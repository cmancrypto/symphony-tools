import bech32

def convert_address(address: str, new_prefix: str) -> str:
    """
    Convert a bech32 address to a new prefix.

    Args:
        address (str): The original bech32 address
        new_prefix (str): The new prefix to convert the address to

    Returns:
        str: The converted bech32 address with the new prefix

    Raises:
        ValueError: If the input address is invalid
    """
    hrp, data = bech32.bech32_decode(address)
    if hrp is None or data is None:
        raise ValueError(f"Invalid bech32 address: {address}")
    return bech32.bech32_encode(new_prefix, data)

def convert_addresses(input_file: str, new_prefix: str, output_file: str) -> int:
    """
    Convert addresses from an input file to a new prefix and write to an output file.

    Args:
        input_file (str): Path to the input text file containing original addresses
        new_prefix (str): The new bech32 prefix to convert addresses to
        output_file (str): Path to the output text file for converted addresses

    Returns:
        int: Number of successfully converted addresses

    Raises:
        FileNotFoundError: If the input file is not found
        PermissionError: If there's a permission issue with reading/writing files
    """
    with open(input_file, 'r') as f:
        addresses = f.read().splitlines()

    converted_addresses = []
    for addr in addresses:
        try:
            converted = convert_address(addr.strip(), new_prefix)
            converted_addresses.append(converted)
        except ValueError as e:
            print(f"Warning: Skipping invalid address '{addr}': {str(e)}")

    with open(output_file, 'w') as f:
        f.write('\n'.join(converted_addresses))

    return len(converted_addresses)