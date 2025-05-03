# LocationFinder

A powerful Python-based reverse geocoding utility that determines location information from geographic coordinates (latitude and longitude). This tool works in both online and offline modes, providing location data even without internet connectivity.

## Features

- **Dual-operation mode**: Online API (OpenStreetMap) with offline fallback
- **Smart location detection**:
  - Automatic location detection based on IP address
  - Manual coordinate input support
  - Command-line coordinate input
- **Intelligent location ranking**:
  - Population-weighted scoring
  - Administrative importance consideration
  - Distance-based evaluation
- **Comprehensive output**:
  - City, state, and country information
  - Distance calculation
  - Precision and confidence indicators
  - Population data (when available)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/mrchandrayee/LocationFinder.git
   cd location
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Ensure the `worldcities.csv` database file is in the same directory as the script.

## Usage

### Basic Usage

Run the script without arguments to attempt automatic location detection:

```
python reverse_geocode.py
```

### Providing Coordinates

Specify coordinates as command-line arguments:

```
python reverse_geocode.py 40.7128 -74.0060
```

### Interactive Mode

If automatic detection fails and no coordinates are specified, the program will prompt for manual input.

## Output Example

```
Automatic coordinates: (37.7749, -122.4194)
Automatic location results:
Location: San Francisco, California, United States
Distance: 0 km
Precision: Exact Match
Confidence: Very High
Population: 3792621
Exact coordinates: (37.7749, -122.4194)
```

## Offline Database

The offline database (`worldcities.csv`) contains comprehensive city data including:
- City name
- State/province
- Country
- Population
- Geographic coordinates
- Administrative importance

## Technical Details

- Earth radius used: 6371 km
- Default search radius: 100 km
- Population weighting factor: 0.3
- Minimum population threshold for primary results: 10,000
- Special weighting for capital cities and administrative centers

## Requirements

- Python 3.6+
- requests
- geocoder

## License



## Acknowledgements

- Data sourced from public geographic databases
- OpenStreetMap Nominatim service for online geocoding
