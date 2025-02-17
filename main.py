import streamlit as st
import pandas as pd
import re
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderUnavailable

def find_address_column(df):
    """
    Determine the best candidate for an address column
    """
    patterns = {
        r".*address.*": 4,
        r".*addr.*": 3,
        r".*street.*": 3,
        r".*location.*": 2,
        r".*residence.*": 2,
        r".*house.*": 1,
        r".*road.*": 2,
        r".*plaza.*": 1,
        r".*avenue.*": 2
    }

    best_score = 0
    best_col = None

    for col in df.columns:
        if df[col].dtype != 'object':
            continue

        score = 0
        col_lower = col.lower()
        # Add weights from regex pattern matches
        for pattern, weight in patterns.items():
            if re.search(pattern, col_lower):
                score += weight

        non_null_values = df[col].dropna()
        if not non_null_values.empty:
            avg_length = non_null_values.map(lambda x: len(x) if isinstance(x, str) else 0).mean()
            if avg_length < 10 or avg_length > 150:
                score -= 2  

        if score > best_score:
            best_score = score
            best_col = col

    return best_col

# Set up the Streamlit app
st.title("Latitude/Longitude Converter")
st.write("Upload a CSV file with addresses. The app will attempt to find the address column automatically, geocode the addresses, and provide the results for download.")

# File uploader widget
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("### Preview of the Uploaded Data:")
    st.write(df.head())

    address_column = find_address_column(df)

    if not address_column:
        st.error("No suitable column containing address information was found. Please check your file or rename the columns accordingly.")
    else:
        st.write(f"**Detected address column:** `{address_column}`")

        # Optional: Let the user override the detected column if needed
        manual_col = st.selectbox("If the detected address column is not correct, select the correct one:", options=[address_column] + [col for col in df.columns if col != address_column])
        if manual_col:
            address_column = manual_col

        if st.button("Geocode Addresses"):
            # Increase the timeout to 10 seconds to help avoid read timeouts
            geolocator = Nominatim(user_agent="streamlit_geocoder", timeout=10)
            # Increase max_retries and error_wait_seconds to handle temporary issues gracefully
            geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1, max_retries=3, error_wait_seconds=2)

            latitudes = []
            longitudes = []

            for addr in df[address_column]:
                # Skip rows with empty or null addresses
                if pd.isna(addr) or (isinstance(addr, str) and addr.strip() == ""):
                    latitudes.append("missing information")
                    longitudes.append("missing information")
                    continue

                try:
                    location = geocode(addr)
                    if location:
                        latitudes.append(location.latitude)
                        longitudes.append(location.longitude)
                    else:
                        latitudes.append("missing information")
                        longitudes.append("missing information")
                except GeocoderUnavailable as e:
                    st.error(f"Error geocoding address '{addr}': {e}")
                    latitudes.append("missing information")
                    longitudes.append("missing information")

            # Populate the DataFrame with new Latitude and Longitude columns
            df['Latitude'] = latitudes
            df['Longitude'] = longitudes

            st.write("### Geocoding Complete! Here's the updated DataFrame:")
            st.write(df.head())

            # Provide a download button for the updated CSV file
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download updated CSV",
                data=csv,
                file_name='geocoded_addresses.csv',
                mime='text/csv',
            )
