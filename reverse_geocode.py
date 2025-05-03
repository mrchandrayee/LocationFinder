import sys
import csv
import math
import requests
import geocoder
import os
from typing import List, Dict, Tuple, Optional
import xml.etree.ElementTree as ET

class LocationFinder:
    def __init__(self):
        self.headers = {'User-Agent': 'LocationFinder/1.0 (aether@gmail.com)'}
        self.offline_db = 'worldcities.csv'  
        self.earth_radius_km = 6371  # Earth's radius in kilometers
        # Default settings for offline geocoding
        self.default_search_radius = 100  # Increased from 50 to 100 km
        self.population_weight = 0.3  # Increased weight for population in scoring
        self.min_population = 10000  # Minimum population for primary results
        self.capital_boost = 0.7  # Boost factor for capital cities
        self.admin_center_boost = 0.8  # Boost factor for administrative centers
        # Cache of important cities by country - will be populated dynamically
        self.important_cities = {}

    def parse_csv_data(self):
        """Parse CSV file for global city data"""
        try:
            with open(self.offline_db, 'r', encoding='utf-8') as f:
                return list(csv.DictReader(f))
        except Exception as e:
            print(f"CSV parse error: {e}")
            return []
    
    def load_important_cities(self, country: str, max_cities: int = 5) -> Dict:
        """
        Dynamically identify important cities for a country from the CSV data
        Returns a dictionary of city names to coordinates
        """
        if country in self.important_cities:
            return self.important_cities[country]
            
        csv_data = self.parse_csv_data()
        if not csv_data:
            return {}
        
        # Filter by country and sort by population
        country_cities = [city for city in csv_data if city.get('country', '') == country]
        country_cities.sort(key=lambda x: int(x.get('population', 0) or 0), reverse=True)
        
        # Get top cities and convert to our format
        important_cities = {}
        for city in country_cities[:max_cities]:
            try:
                city_name = city.get('city', '')
                important_cities[city_name] = {
                    'lat': float(city.get('lat', 0)),
                    'lng': float(city.get('lng', 0))
                }
            except (ValueError, KeyError):
                continue
                
        # Cache for future use
        self.important_cities[country] = important_cities
        return important_cities
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points 
        on the Earth's surface specified in decimal degrees.
        Returns distance in kilometers.
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Return distance in kilometers
        return self.earth_radius_km * c
    
    def calculate_score(self, distance: float, location: dict) -> float:
        """
        Calculate a combined score based on distance, population and other contextual factors.
        Lower score is better.
        """
        # Get basic info
        population = int(location.get('population', 0) or 0)
        city_name = location.get('city', '').strip()
        country = location.get('country', '').strip()
        
        # Start with distance as base score
        score = distance
        
        # Population factor (larger cities get preference)
        if population > 0:
            # Logarithmic scale for population - prevents megacities from dominating completely
            pop_factor = 1.0 - min(1.0, math.log10(population) / 8.0) * self.population_weight
            score *= pop_factor
        
        # Check if it's a capital or major city
        if location.get('capital', '').lower() == 'primary':
            score *= self.capital_boost
            
        # Check if city is an administrative center
        if location.get('capital', '').lower() in ('admin', 'minor'):
            score *= self.admin_center_boost
            
        # Check against important cities in the region (dynamically loaded)
        important_cities = self.load_important_cities(country)
        if important_cities:
            for major_city, coords in important_cities.items():
                # If city name matches or is similar to a major city
                if (major_city.lower() in city_name.lower() or 
                    city_name.lower() in major_city.lower()):
                    
                    # Calculate distance to the known coordinates of the major city
                    known_distance = self.haversine_distance(
                        float(location.get('lat')), float(location.get('lng')), 
                        coords['lat'], coords['lng']
                    )
                    
                    # If coordinates are very close to known coordinates, boost score
                    if known_distance < 3:  # Within 3km
                        score *= 0.85  # Significant boost
                        
        return score

    def find_nearest_locations(self, latitude: float, longitude: float, 
                             max_results: int = 10, 
                             max_distance_km: float = None,
                             min_population: int = None) -> List[Dict]:
        """
        Find the nearest locations to the given coordinates with improved accuracy.
        Returns a list of dictionaries with location information, distance, and score.
        """
        # Use default values if not specified
        max_distance_km = max_distance_km or self.default_search_radius
        min_population = min_population or 0
        
        csv_data = self.parse_csv_data()
        if not csv_data:
            return []
        
        # Calculate distances for all locations
        locations_with_distance = []
        small_locations = []  # For locations below the min_population threshold
        
        for location in csv_data:
            try:
                loc_lat = float(location['lat'])
                loc_lng = float(location['lng'])
                population = int(location.get('population', 0) or 0)
                
                # Calculate distance
                distance = self.haversine_distance(latitude, longitude, loc_lat, loc_lng)
                
                # Only include locations within the specified max distance
                if distance <= max_distance_km:
                    location_info = {
                        'city': location.get('city', 'Unknown'),
                        'state': location.get('admin_name', ''),
                        'country': location.get('country', ''),
                        'population': population,
                        'capital': location.get('capital', ''),
                        'distance_km': round(distance, 2),
                        'lat': loc_lat,
                        'lng': loc_lng,
                    }
                    
                    # Calculate the score with improved algorithm
                    location_info['score'] = self.calculate_score(distance, location_info)
                    
                    # Separate into two groups based on population
                    if population >= self.min_population:
                        locations_with_distance.append(location_info)
                    else:
                        small_locations.append(location_info)
            except (ValueError, KeyError):
                continue
        
        # Sort by calculated score
        locations_with_distance.sort(key=lambda x: x['score'])
        
        # If we don't have enough major locations, include smaller ones sorted by score
        if len(locations_with_distance) < max_results:
            small_locations.sort(key=lambda x: x['score'])
            locations_with_distance.extend(small_locations[:max_results - len(locations_with_distance)])
        
        # Return top results, limited by max_results
        return locations_with_distance[:max_results]

    def determine_most_accurate_location(self, locations: List[Dict], latitude: float, longitude: float) -> Dict:
        """
        Determines the most accurate location from a list of candidates.
        Uses advanced heuristics to select the best match.
        """
        if not locations:
            return {'error': 'No locations found'}
            
        # If we only have one location, that's our answer
        if len(locations) == 1:
            return locations[0]
            
        # Get the top 3 locations by score
        top_locations = locations[:3]
        
        # Check if we have a clear winner (significantly better score)
        if len(top_locations) > 1 and top_locations[0]['score'] < top_locations[1]['score'] * 0.7:
            return top_locations[0]
            
        # For close matches, prefer:
        # 1. Locations with higher population
        # 2. Administrative centers
        # 3. Closer locations
        
        # Create a final score that weights these factors
        for loc in top_locations:
            final_score = loc['score']
            
            # Population bonus (log scale)
            if loc['population'] > 0:
                final_score *= (1 - min(0.3, math.log10(loc['population']) / 10))
                
            # Administrative center bonus
            if loc.get('capital') == 'admin':
                final_score *= 0.85
            elif loc.get('capital') == 'primary':
                final_score *= 0.8
                
            # Very close locations get an extra boost
            if loc['distance_km'] < 5:
                final_score *= (1 - (5 - loc['distance_km']) * 0.05)
                
            loc['final_score'] = final_score
            
        # Return the location with the best final score
        return min(top_locations, key=lambda x: x['final_score'])

    def reverse_geocode(self, latitude: float, longitude: float) -> dict:
        try:
            # Try online API first
            print("Attempting online reverse geocoding...")
            response = requests.get(
                f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}",
                headers=self.headers,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            
            address = data.get('address', {})
            city = address.get('city') or address.get('town') or address.get('village') or address.get('state_district') or address.get('county')
            state = address.get('state')
            country = address.get('country')
            
            # Return a consistent result structure regardless of source (online or offline)
            return {
                'city': city,
                'state': state,
                'country': country,
                'distance_km': 0,  # 0 distance as this is from the exact coordinates
                'precision': 'Exact Match',
                'accuracy_rating': 'Very High',
                'exact_coordinates': {
                    'latitude': latitude,
                    'longitude': longitude
                },
                'source': 'Online API'
            }
        except requests.exceptions.RequestException as e:
            print(f"Online API failed: {e}")
            print("Switching to offline database...")
            
            # Get nearest locations with improved accuracy
            nearest_locations = self.find_nearest_locations(
                latitude, longitude,
                max_results=10, 
                max_distance_km=self.default_search_radius
            )
            
            if not nearest_locations:
                # Try a wider search if no results found
                nearest_locations = self.find_nearest_locations(
                    latitude, longitude,
                    max_results=5, 
                    max_distance_km=self.default_search_radius * 2,
                    min_population=0
                )
                
            if not nearest_locations:
                return {'error': 'No matching locations in offline data'}
            
            # Determine the most accurate location using our enhanced algorithm
            most_accurate_location = self.determine_most_accurate_location(nearest_locations, latitude, longitude)
            
            # Return the most accurate location with additional context
            result = {
                'city': most_accurate_location['city'],
                'state': most_accurate_location['state'],
                'country': most_accurate_location['country'],
                'distance_km': most_accurate_location['distance_km'],
                'precision': self._calculate_precision(most_accurate_location['distance_km']),
                'accuracy_rating': self._calculate_confidence(most_accurate_location['distance_km'], most_accurate_location.get('population', 0)),
                'exact_coordinates': {
                    'latitude': most_accurate_location['lat'],
                    'longitude': most_accurate_location['lng']
                },
                'source': 'Offline Database'
            }
            
            # Add population info if available
            if most_accurate_location['population'] > 0:
                result['population'] = most_accurate_location['population']
                
            return result
    
    def _calculate_precision(self, distance_km: float) -> str:
        """Calculate precision indicator based on distance"""
        if distance_km < 2:
            return "Exact Match"
        elif distance_km < 5:
            return "Very Precise"
        elif distance_km < 10:
            return "Precise"
        elif distance_km < 25:
            return "Approximate"
        else:
            return "General Area"
    
    def _calculate_confidence(self, distance_km: float, population: int = 0) -> str:
        """Calculate a confidence level based on distance and population"""
        # Base confidence on distance
        if distance_km < 3:
            confidence = "Very High"
        elif distance_km < 10:
            confidence = "High"
        elif distance_km < 25:
            confidence = "Medium"
        else:
            confidence = "Low"
            
        # Adjust based on population
        if population > 1000000 and confidence != "Very High":
            # Increase confidence for major cities
            if confidence == "High":
                confidence = "Very High"
            elif confidence == "Medium":
                confidence = "High"
            elif confidence == "Low":
                confidence = "Medium"
                
        return confidence

    def get_auto_coordinates(self) -> tuple:
        """Get coordinates through IP geolocation with error handling"""
        try:
            # Try alternative geocoding service with timeout
            print("Attempting to find your location automatically...")
            g = geocoder.ip('me', timeout=10)
            if not g.latlng:
                raise RuntimeError("No coordinates found")
            return g.latlng
        except Exception as e:
            raise RuntimeError(f"Network error: Check internet connection\nOriginal error: {str(e)}") from e

    @staticmethod
    def get_manual_coordinates() -> tuple:
        """Get coordinates through user input"""
        try:
            lat = float(input("Enter latitude: "))
            lon = float(input("Enter longitude: "))
            return (lat, lon)
        except ValueError as e:
            raise ValueError("Invalid input: Numbers required") from e

if __name__ == "__main__":
    finder = LocationFinder()
    coords = None
    mode = "Automatic"

    # First try command-line arguments
    if len(sys.argv) == 3:
        try:
            coords = (float(sys.argv[1]), float(sys.argv[2]))
            mode = "Manual (CLI)"
        except ValueError:
            print("Invalid command-line arguments: Please provide numeric latitude and longitude")

    # Then try automatic detection
    if not coords:
        try:
            coords = finder.get_auto_coordinates()
            mode = "Automatic"
        except RuntimeError as e:
            print(f"\n⚠️ Automatic detection failed: {str(e)}")

    # Finally try interactive manual input
    if not coords:
        print("\nPlease enter coordinates manually:")
        try:
            coords = LocationFinder.get_manual_coordinates()
            mode = "Manual (Interactive)"
        except ValueError as e:
            print(f"Error: {e}")
            coords = None

    if coords:
        print(f"\n{mode} coordinates: {coords}")
        try:
            result = finder.reverse_geocode(coords[0], coords[1])
            print(f"{mode} location results:")
            
            # Format the output to focus on the final location without showing alternates
            if 'error' in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Location: {result['city']}, {result['state']}, {result['country']}")
                print(f"Distance: {result['distance_km']} km")
                print(f"Precision: {result['precision']}")
                print(f"Confidence: {result['accuracy_rating']}")
                if 'population' in result:
                    print(f"Population: {result['population']}")
                print(f"Exact coordinates: ({result['exact_coordinates']['latitude']}, {result['exact_coordinates']['longitude']})")
        except RuntimeError as e:
            print(f"Geocoding error: {e}")
    else:
        print("Failed to retrieve coordinates through all available methods")
