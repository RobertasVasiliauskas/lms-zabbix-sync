import sys
from geopy.geocoders import Nominatim
import logging
from geopy.exc import GeocoderTimedOut
from time import sleep

logger = logging.getLogger(__name__)

def get_city_by_zip(zip_code: str) -> str:
    geolocator = Nominatim(user_agent="address_lookup", timeout=10)  # Increased timeout to 10 seconds

    retries = 3
    for attempt in range(retries):
        try:
            location = geolocator.geocode({"postalcode": zip_code}, country_codes="lt", exactly_one=True)
            if location is not None:
                print("Location Raw:", location.raw)
                address = location.raw.get("address", {})
                display_name = location.raw.get("display_name", "")
                city = address.get("city") or address.get("town") or address.get("village")
                if city:
                    return city
                if display_name:
                    parts = display_name.split(",")
                    for part in parts:
                        part = part.strip()
                        if "seniūnija" not in part.lower() and "apskritis" not in part.lower() and part != zip_code:
                            if len(part) > 2 and not part.isdigit():
                                return part
                municipality = address.get("municipality")
                if municipality and "savivaldybė" not in municipality.lower():
                    return municipality
                logger.warning(f"Could not determine city for ZIP {zip_code}.")
                return "City not found"
            else:
                logger.error(f"Could not find location for ZIP {zip_code}.")
                return "Location not found"
        except GeocoderTimedOut as e:
            if attempt < retries - 1:
                logger.warning(f"Timeout for ZIP {zip_code}, retrying... ({attempt + 1}/{retries})")
                sleep(1)
                continue
            logger.error(f"Error retrieving address for ZIP {zip_code}: {e}")
            return "Error"
        except Exception as e:
            logger.error(f"Error retrieving address for ZIP {zip_code}: {e}")
            return "Error"

if __name__ == "__main__":
    zip_codes = ["17132", "01108", "28143", "17139", "45462"]
    for zip_code in zip_codes:
        city = get_city_by_zip(zip_code)
        print(f"ZIP: {zip_code} -> City: {city}")