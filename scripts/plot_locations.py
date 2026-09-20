import folium

locations = {
    "Boston": [
        (42.42634, -71.07327),
        (42.35516, -71.05980),
        (42.37266, -71.11842),
        (42.34043, -71.08790),
        (42.36430, -71.02078),
    ],
    "Atlanta": [
        (33.75960, -84.39310),
        (33.75830, -84.38710),
        (33.75745, -84.38240),
        (33.77410, -84.39900),
        (33.78100, -84.40013),
    ],
    "Philadelphia": [
        (39.95481, -75.19760),
        (39.95343, -75.15691),
    ],
}

# Center the map on the US, zoomed to show all three cities
m = folium.Map(location=[38.5, -78.0], zoom_start=6, tiles="OpenStreetMap")

for city, coords in locations.items():
    for idx, (lat, lon) in enumerate(coords, start=1):
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color="red", icon="circle", prefix="fa"),
            popup=folium.Popup(f"<b>{city}</b><br>Location {idx}<br>({lat}, {lon})", max_width=200),
            tooltip=f"{city} – Loc {idx}",
        ).add_to(m)

# Add a simple legend as an HTML element
legend_html = """
<div style="
    position: fixed;
    bottom: 40px; left: 40px;
    background-color: white;
    border: 2px solid grey;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 14px;
    z-index: 9999;
    box-shadow: 3px 3px 6px rgba(0,0,0,0.3);
">
    <b>Test Locations</b><br>
    <span style="color:red;">&#9679;</span> Boston (5 sites)<br>
    <span style="color:red;">&#9679;</span> Atlanta (5 sites)<br>
    <span style="color:red;">&#9679;</span> Philadelphia (2 sites)
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

output_path = "test_locations_map.html"
m.save(output_path)
print(f"Map saved to {output_path}")
