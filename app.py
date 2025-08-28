import streamlit as st
import pandas as pd
import pydeck as pdk
from datetime import datetime

# Optional geocoding (internet required). App works without it via manual lat/lon entry.
try:
    from geopy.geocoders import Nominatim
    geocoder = Nominatim(user_agent="halifax-community-map")
except Exception:
    geocoder = None

# ---------------------------
# App Config
# ---------------------------
st.set_page_config(page_title="Community Map of Halifax, NC", layout="wide")
st.title("📍 Community Map of Halifax (NC)")
st.caption("Add pins for favorite local spots — food, sports, study places, hangouts, nature, and more.")

# Halifax, North Carolina (approximate center)
DEFAULT_CENTER = {"lat": 36.33, "lon": -77.59}

# Initialize state
if "pins" not in st.session_state:
    st.session_state.pins = []

# ---------------------------
# Helper Functions
# ---------------------------
CATEGORIES = [
    "Food",
    "Sports",
    "Study Spot",
    "Hangout",
    "Nature/Outdoors",
    "Volunteering",
    "Other",
]

CATEGORY_COLORS = {
    "Food": [255, 99, 132],
    "Sports": [54, 162, 235],
    "Study Spot": [255, 206, 86],
    "Hangout": [75, 192, 192],
    "Nature/Outdoors": [153, 102, 255],
    "Volunteering": [255, 159, 64],
    "Other": [200, 200, 200],
}


def pins_df() -> pd.DataFrame:
    if not st.session_state.pins:
        return pd.DataFrame(columns=[
            "name", "category", "description", "address", "lat", "lon", "likes", "added_at"
        ])
    return pd.DataFrame(st.session_state.pins)


def add_pin(name: str, category: str, description: str, address: str, lat: float, lon: float):
    st.session_state.pins.append({
        "name": name.strip(),
        "category": category,
        "description": description.strip(),
        "address": address.strip(),
        "lat": float(lat),
        "lon": float(lon),
        "likes": 0,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


def geocode(address: str):
    if not address or geocoder is None:
        return None
    try:
        loc = geocoder.geocode(address)
        if loc:
            return {"lat": loc.latitude, "lon": loc.longitude}
    except Exception:
        return None
    return None


def map_view(df: pd.DataFrame, use_heatmap: bool):
    if df.empty:
        st.info("No pins yet. Add your first spot on the left!")
        return

    df = df.copy()
    df["color"] = df["category"].apply(lambda c: CATEGORY_COLORS.get(c, [200, 200, 200]))

    layers = []
    if use_heatmap:
        layers.append(
            pdk.Layer(
                "HeatmapLayer",
                data=df,
                get_position='[lon, lat]',
                aggregation= "MEAN",
                radiusPixels= 60,
            )
        )

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position='[lon, lat]',
            get_radius=50,
            radius_min_pixels=5,
            radius_max_pixels=60,
            get_fill_color="color",
            pickable=True,
        )
    )

    tooltip = {
        "html": "<b>{name}</b><br/>Category: {category}<br/>{description}",
        "style": {"backgroundColor": "#0f172a", "color": "white"}
    }

    view_state = pdk.ViewState(
        latitude=float(df["lat"].mean()) if len(df) else DEFAULT_CENTER["lat"],
        longitude=float(df["lon"].mean()) if len(df) else DEFAULT_CENTER["lon"],
        zoom=12,
        pitch=0,
    )

    r = pdk.Deck(
        map_style="mapbox://styles/mapbox/streets-v12",
        initial_view_state=view_state,
        layers=layers,
        tooltip=tooltip,
    )
    st.pydeck_chart(r, use_container_width=True)


# ---------------------------
# Sidebar: Add & Manage Pins
# ---------------------------
st.sidebar.header("Add a Place")
with st.sidebar.form("add_pin_form"):
    name = st.text_input("Place name *", placeholder="Ex: Ralph's Barbecue")
    category = st.selectbox("Category", options=CATEGORIES, index=0)
    description = st.text_area("Why is it awesome?", placeholder="What makes this place great?")
    address = st.text_input("Address (optional)", placeholder="Street, Halifax, NC")
    col_a, col_b = st.columns(2)
    with col_a:
        lat = st.number_input("Latitude", value=DEFAULT_CENTER["lat"], format="%.6f")
    with col_b:
        lon = st.number_input("Longitude", value=DEFAULT_CENTER["lon"], format="%.6f")

    use_geocode = st.checkbox("Try to auto-fill lat/lon from address", value=True, help="Requires internet access")
    submitted = st.form_submit_button("➕ Add to Map", use_container_width=True)

    if submitted:
        if not name.strip():
            st.warning("Please provide a place name.")
        else:
            # If address provided and geocoding enabled, try to fetch coordinates
            if use_geocode and address.strip():
                loc = geocode(address + ", Halifax, North Carolina")
                if loc is not None:
                    lat, lon = loc["lat"], loc["lon"]
            try:
                add_pin(name, category, description, address, lat, lon)
                st.success(f"Added '{name}' to the map!")
            except Exception as e:
                st.error(f"Could not add pin: {e}")

st.sidebar.divider()

# CSV Import/Export
st.sidebar.subheader("Import / Export")
upload = st.sidebar.file_uploader("Import pins CSV", type=["csv"], help="Columns: name,category,description,address,lat,lon,likes,added_at")
if upload is not None:
    try:
        df_up = pd.read_csv(upload)
        needed = {"name","category","description","address","lat","lon"}
        if not needed.issubset(set(df_up.columns)):
            st.sidebar.error("CSV missing required columns.")
        else:
            for _, row in df_up.iterrows():
                add_pin(
                    row.get("name",""),
                    row.get("category","Other"),
                    str(row.get("description","")),
                    str(row.get("address","")),
                    float(row.get("lat", DEFAULT_CENTER["lat"])),
                    float(row.get("lon", DEFAULT_CENTER["lon"]))
                )
            st.sidebar.success("Imported pins from CSV!")
    except Exception as e:
        st.sidebar.error(f"Import failed: {e}")

current_df = pins_df()

csv_data = current_df.to_csv(index=False).encode("utf-8")
st.sidebar.download_button(
    "⬇️ Download pins CSV",
    data=csv_data,
    file_name="halifax_pins.csv",
    mime="text/csv",
    use_container_width=True,
)

# ---------------------------
# Main Area: Filters + Map
# ---------------------------
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Map")
    toggles = st.columns(3)
    with toggles[0]:
        use_heatmap = st.toggle("Heatmap", value=False)
    with toggles[1]:
        show_table = st.toggle("Show table", value=True)
    with toggles[2]:
        center_default = st.toggle("Center on Halifax", value=False)

    df = current_df.copy()
    if center_default or df.empty:
        view_center = DEFAULT_CENTER
    else:
        view_center = {"lat": float(df["lat"].mean()), "lon": float(df["lon"].mean())}

    map_view(df, use_heatmap)

with col2:
    st.subheader("Filters")
    chosen = st.multiselect("Show categories", options=CATEGORIES, default=CATEGORIES)
    query = st.text_input("Search name/description")

    filtered = current_df.copy()
    if chosen:
        filtered = filtered[filtered["category"].isin(chosen)]
    if query.strip():
        q = query.strip().lower()
        filtered = filtered[
            filtered["name"].str.lower().str.contains(q) |
            filtered["description"].str.lower().str.contains(q)
        ]

    st.metric("Pins visible", len(filtered))

    if not filtered.empty:
        st.caption("Click a row for details below.")
        st.dataframe(
            filtered[["name","category","description","address","lat","lon","likes","added_at"]]
            .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )

# ---------------------------
# Interact: Like & Details
# ---------------------------
st.subheader("Spotlight & Shoutouts")
if filtered.empty:
    st.info("No matching spots yet. Try different filters or add a place!")
else:
    for i, row in filtered.reset_index(drop=True).iterrows():
        with st.expander(f"{row['name']} — {row['category']}"):
            st.write(row["description"] or "No description provided.")
            st.write(f"**Address:** {row['address'] or '—'}")
            gmaps = f"https://www.google.com/maps/search/?api=1&query={row['lat']},{row['lon']}"
            st.markdown(f"[Open in Google Maps]({gmaps})")

            cols = st.columns(3)
            with cols[0]:
                if st.button("❤️ Like", key=f"like_{i}"):
                    # Find the exact item in session_state and increment
                    for pin in st.session_state.pins:
                        if (
                            pin["name"] == row["name"]
                            and pin["lat"] == row["lat"]
                            and pin["lon"] == row["lon"]
                            and pin["category"] == row["category"]
                        ):
                            pin["likes"] = int(pin.get("likes", 0)) + 1
                            break
                    st.rerun()
            with cols[1]:
                st.write(f"👍 Likes: {row['likes']}")
            with cols[2]:
                st.write(f"🗓 Added: {row['added_at']}")

# ---------------------------
# Starter Pins (optional)
# ---------------------------
if not st.session_state.pins:
    st.info("Need ideas? Add Ralph's Barbecue (w/ address) or the Halifax County Courthouse to get started.")
