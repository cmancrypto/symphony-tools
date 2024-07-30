# Symphony Tools

Symphony Tools is a Python package that provides utilities for working with Cosmos-based blockchains. It includes two main modules:

1. Bech32 Converter: For converting Cosmos bech32 addresses between different prefixes.
2. Snapshot Tools: For handling blockchain snapshots.

## Installation

Install requirements:

```pip install -r requirements.txt```

Install Symphony Tools using pip:

```pip install symphony-tools```

## Bech32 Converter

### Command-line Usage

Convert addresses using the command-line interface:

```symphony-bech32 <input_file> <new_prefix> <output_file>```

example: 
```symphony-bech32 old_file.txt symphony new_file.txt ```
