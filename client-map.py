import pandas as pd
import streamlit as st
import requests
import folium
from streamlit_folium import folium_static
from opencage.geocoder import OpenCageGeocode

# Replace with your own OpenCage API key
OPEN_CAGE_API_KEY = st.secrets["API_KEY"]

# =============================================================================
# Caching functions to speed up repeated runs
# =============================================================================

@st.cache_data(show_spinner=False)
def load_data():
    """Load client data from CSV."""
    url = "http://metabase.prod.tessan.cloud/public/question/6c3c45ab-7379-4815-8941-dcd6763c555c.csv"
    clients = pd.read_csv(url)
    return clients

@st.cache_data(show_spinner=False)
def get_geocode(query, api_key=OPEN_CAGE_API_KEY):
    """
    Get latitude and longitude for a given address using the OpenCage API.
    
    Parameters:
        query (str): The address to geocode.
        api_key (str): Your OpenCage API key.
    
    Returns:
        tuple: (latitude, longitude) or (None, None) if not found.
    """
    geocoder = OpenCageGeocode(api_key)
    try:
        result = geocoder.geocode(query)
        if result and len(result) > 0:
            return result[0]['geometry']['lat'], result[0]['geometry']['lng']
        else:
            return None, None
    except Exception as e:
        st.error(f"Error geocoding {query}: {e}")
        return None, None

# =============================================================================
# Main App
# =============================================================================

def main():
    st.title("Clients TESSAN")

    # Load data and drop rows missing an Address
    data = load_data()
    data = data.dropna(subset=['Address'])
    
    # ----------------------------------------------------------------------
    # Sidebar: Multi-Select Department Filter with Search
    # ----------------------------------------------------------------------
    st.sidebar.header("Filtre")

    # Get unique departments from data
    departments = sorted(data['AdministrativeArea2'].dropna().unique().tolist())

    # Multi-select filter: all departments selected by default
    selected_departments = st.sidebar.multiselect(
        "Sélectionnez un ou plusieurs départements",
        options=departments,
        default=[], #No preselected departments
    )

    # Filter data based on selected departments
    if selected_departments:
        data = data[data['AdministrativeArea2'].isin(selected_departments)]

    # If no data remains after filtering, notify the user
    if data.empty:
        st.warning("Aucune donnée disponible après application du filtre.")
        return

    # ----------------------------------------------------------------------
    # Geocode Addresses (only for filtered data)
    # ----------------------------------------------------------------------
    data[['lat', 'lng']] = data['Address'].apply(lambda x: pd.Series(get_geocode(x)))
    
    # Remove rows where geocoding failed
    data = data.dropna(subset=['lat', 'lng'])

    if data.empty:
        st.warning("Aucune donnée valide après géocodage.")
        return

    # ----------------------------------------------------------------------
    # Build and Display the Map using Folium
    # ----------------------------------------------------------------------

    # Load French departments GeoJSON
    geojson_url = 'https://france-geojson.gregoiredavid.fr/repo/departements.geojson'
    departements_geojson = requests.get(geojson_url).json()

    # Center the map on the average location of the clients
    average_lat = data['lat'].mean()
    average_lon = data['lng'].mean()
    folium_map = folium.Map(location=[average_lat, average_lon], zoom_start=6)

    # Add GeoJSON overlay for French departments
    folium.GeoJson(
        departements_geojson,
        name="French Departments",
        style_function=lambda x: {
            "fillColor": "orange",
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.2,
        },
    ).add_to(folium_map)

    # Add markers for each client
    for _, row in data.iterrows():
        popup_content = f"""
        <b>Name:</b> {row['Name']}<br>
        <b>Address:</b> {row['Address']}<br>
        <b>Department:</b> {row['AdministrativeArea2']}<br>
        """
        folium.Marker(
            location=[row['lat'], row['lng']],
            popup=popup_content,
            icon=folium.Icon(color='darkgreen'),
        ).add_to(folium_map)

    # Save the map as an HTML file
    map_filename = "client_map.html"
    folium_map.save(map_filename)

    # Display the Folium map in Streamlit
    folium_static(folium_map)

    # ----------------------------------------------------------------------
    # Download Button for the Map
    # ----------------------------------------------------------------------
    with open(map_filename, "r", encoding="utf-8") as file:
        html_data = file.read()

    st.download_button(
        label="Télécharger la carte",
        data=html_data,
        file_name="client_map.html",
        mime="text/html",
    )

    # ----------------------------------------------------------------------
    # Display Data Table
    # ----------------------------------------------------------------------
    st.subheader("Tableau des Données")
    st.dataframe(data[['Name', 'Address', 'AdministrativeArea2', 'lat', 'lng']], height=300)

if __name__ == '__main__':
    main()