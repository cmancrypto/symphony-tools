"""Process and analyze staking data from multiple Cosmos SDK chains."""

import requests
import pandas as pd
from decimal import Decimal
import bech32
import concurrent.futures
from typing import List, Dict, Any, Tuple
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Config
chains = [
    {
        "name": "cosmos",
        "api_url": "https://rest.cosmos.directory/cosmoshub",
        "prefix": "cosmos",
        "stake_threshold": Decimal("15000000")  # 15 ATOM
    },
    {
        "name": "osmosis",
        "api_url": "https://rest.cosmos.directory/osmosis",
        "prefix": "osmo",
        "stake_threshold": Decimal("150000000")  # 150 OSMO
    },
    # Add more chains as needed
]
output_prefix = "symphony"  # The prefix to convert all addresses to
max_workers = 10  # Adjust based on your system's capabilities and expected issues with API
max_retries = 5  # Maximum number of retry attempts
min_wait = 10  # Minimum wait time in seconds
max_wait = 60  # Maximum wait time in seconds
delegator_pagination_limit = str(10000) # How many delegation results to return per page
# Configure Loguru
logger.add("cosmos_staking_analysis.log", rotation="10 MB")


def get_all_validators(api_url: str) -> List[str]:
    """
    Fetch all validator addresses from a Cosmos SDK chain.

    Args:
        api_url (str): The base URL for the chain's API.

    Returns:
        List[str]: A list of validator addresses.
    """
    logger.info(f"Fetching validators from {api_url}")
    validators = []
    next_key = None
    page = 1

    while True:
        logger.debug(f"Fetching page {page} of validators")
        endpoint = f"{api_url}/cosmos/staking/v1beta1/validators"
        params = {"pagination.limit": "1000"}
        if next_key:
            params["pagination.key"] = next_key

        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()

        validators.extend([v['operator_address'] for v in data["validators"]])
        logger.debug(f"Fetched {len(data['validators'])} validators. Total: {len(validators)}")

        next_key = data["pagination"].get("next_key")
        if not next_key:
            break
        page += 1

    logger.info(f"Finished fetching validators. Total validators: {len(validators)}")
    return validators


@retry(stop=stop_after_attempt(max_retries),
       wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
       retry=retry_if_exception_type(requests.exceptions.RequestException),
       reraise=True)
def get_delegators_page(api_url: str, validator_address: str, next_key: str = None) -> Tuple[List[Dict[str, Any]], str]:
    """
    Get a page of delegators for a specific validator with retry logic.

    Args:
        api_url (str): The base URL for the chain's API.
        validator_address (str): The address of the validator.
        next_key (str, optional): The pagination key for the next page.

    Returns:
        Tuple[List[Dict[str, Any]], str]: A tuple containing the list of delegators and the next pagination key.
    """
    endpoint = f"{api_url}/cosmos/staking/v1beta1/validators/{validator_address}/delegations"
    params = {"pagination.limit": "10000"}
    if next_key:
        params["pagination.key"] = next_key

    response = requests.get(endpoint, params=params)
    response.raise_for_status()
    data = response.json()

    delegators = [
        {
            "address": d['delegation']['delegator_address'],
            "validator": validator_address,
            "amount": Decimal(d['balance']['amount'])
        }
        for d in data["delegation_responses"]
    ]

    return delegators, data["pagination"].get("next_key")


def get_delegators_for_validator(args: Tuple[str, str, Decimal]) -> List[Dict[str, Any]]:
    """
    Get delegators and their staked amounts for a specific validator.

    Args:
        args (Tuple[str, str, Decimal]): Tuple containing api_url, validator_address, and stake_threshold.

    Returns:
        List[Dict[str, Any]]: List of delegator data dictionaries.
    """
    api_url, validator_address, stake_threshold = args
    logger.debug(f"Fetching delegators for validator {validator_address}")
    delegators = []
    next_key = None

    while True:
        try:
            page_delegators, next_key = get_delegators_page(api_url, validator_address, next_key)
            delegators.extend([d for d in page_delegators if d['amount'] > stake_threshold])

            if not next_key:
                break
        except Exception as e:
            logger.error(f"Failed to get delegators for validator {validator_address} after all retries: {str(e)}")
            break

    logger.debug(
        f"Finished fetching delegators for validator {validator_address}. Total delegators above threshold: {len(delegators)}")
    return delegators


def convert_address(address: str, from_prefix: str, to_prefix: str) -> str:
    """
    Convert a bech32 address from one prefix to another.

    Args:
        address (str): The address to convert.
        from_prefix (str): The current prefix of the address.
        to_prefix (str): The desired prefix for the address.

    Returns:
        str: The converted address.
    """
    _, data = bech32.bech32_decode(address)
    return bech32.bech32_encode(to_prefix, data)


def process_chain(chain: Dict[str, Any]) -> pd.DataFrame:
    """
    Process a single chain, fetching validators, delegators, and creating a DataFrame.

    Args:
        chain (Dict[str, Any]): A dictionary containing chain information.

    Returns:
        pd.DataFrame: A DataFrame containing processed delegator information.
    """
    logger.info(f"Processing chain: {chain['name']}")
    validators = get_all_validators(chain['api_url'])

    logger.info(f"Fetching delegators for {len(validators)} validators")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(chain['api_url'], validator, chain['stake_threshold']) for validator in validators]
        results = list(executor.map(get_delegators_for_validator, args_list))

    delegators = [item for sublist in results for item in sublist]

    logger.info(f"Creating DataFrame for delegators")
    df = pd.DataFrame(delegators)

    logger.info(f"Aggregating delegations for unique delegators")
    df_aggregated = df.groupby('address').agg({
        'amount': 'sum',
        'validator': lambda x: list(set(x))  # List of unique validators
    }).reset_index()

    #df_aggregated['num_validators'] = df_aggregated['validator'].apply(len)
    df_aggregated['original_address'] = df_aggregated['address']

    logger.info(f"Converting addresses for chain {chain['name']}")
    df_aggregated['address'] = df_aggregated['address'].apply(
        lambda x: convert_address(x, chain['prefix'], output_prefix))
    df_aggregated['chain'] = chain['name']

    # Filter out delegators below threshold after aggregation
    df_filtered = df_aggregated[df_aggregated['amount'] > chain['stake_threshold']]

    logger.info(
        f"Finished processing chain: {chain['name']}. Total unique delegators above threshold: {len(df_filtered)}")
    return df_filtered


def main():
    """Main function to process all chains and generate summary statistics."""
    logger.info("Starting Cosmos staking analysis")

    # Process all chains
    logger.info(f"Processing {len(chains)} chains with {max_workers} workers")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        dfs = list(executor.map(process_chain, chains))

    # Combine all dataframes
    logger.info("Combining DataFrames from all chains")
    combined_df = pd.concat(dfs, ignore_index=True)

    # Display the first few rows of the combined DataFrame
    logger.info("Preview of combined DataFrame:")
    logger.info(combined_df.head().to_string())

    # Save the combined DataFrame to a CSV file
    output_file = "combined_cosmos_delegators_above_threshold.csv"
    logger.info(f"Saving combined DataFrame to {output_file}")
    combined_df.to_csv(output_file, index=False)

    # Print summary for each chain
    logger.info("Generating summary statistics for each chain")
    for chain in chains:
        chain_df = combined_df[combined_df['chain'] == chain['name']]
        logger.info(f"\nChain: {chain['name']}")
        logger.info(f"Unique delegators above threshold: {len(chain_df)}")
        logger.info(f"Average total stake: {chain_df['amount'].mean():.2f}")
        logger.info(f"Median total stake: {chain_df['amount'].median():.2f}")
        logger.info(f"Max total stake: {chain_df['amount'].max():.2f}")
        logger.info(f"Average number of validators per delegator: {chain_df['num_validators'].mean():.2f}")

    # Print overall summary
    logger.info("\nOverall Summary:")
    logger.info(f"Total unique delegators above threshold across all chains: {len(combined_df)}")
    logger.info("Cosmos snapshot completed")


if __name__ == "__main__":
    main()