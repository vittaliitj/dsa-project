
from flask import Flask, request
import folium
import osmnx as ox
import networkx as nx
from geopy.distance import geodesic

app = Flask(__name__)

@app.route('/')
def index():
    return open("index.html").read()

@app.route('/get_route', methods=['POST'])
def get_route():
    try:
        data = request.get_json()
        user_lat = data['lat']
        user_lon = data['lon']
        print(f"[INFO] User Location: {user_lat}, {user_lon}")

        G = ox.graph_from_point((user_lat, user_lon), dist=5000, network_type='drive')
        G = ox.add_edge_speeds(G, fallback=50)
        G = ox.add_edge_travel_times(G)
        orig_node = ox.distance.nearest_nodes(G, user_lon, user_lat)

        tags = {'amenity': ['hospital', 'clinic', 'doctors'], 'healthcare': True}
        hospitals = ox.features_from_point((user_lat, user_lon), tags=tags, dist=5000)
        if hospitals.empty:
            hospitals = ox.features_from_point((user_lat, user_lon), tags=tags, dist=10000)
        if hospitals.empty:
            return "<h3>⚠️ No hospitals or clinics found near your location.</h3>"

        hospitals['dist'] = hospitals.geometry.centroid.apply(
            lambda point: geodesic((user_lat, user_lon), (point.y, point.x)).meters
        )
        nearest = hospitals.sort_values(by='dist').iloc[0]
        hosp_coords = (nearest.geometry.centroid.y, nearest.geometry.centroid.x)
        hospital_name = nearest.get('name', 'Unknown Facility')
        dest_node = ox.distance.nearest_nodes(G, hosp_coords[1], hosp_coords[0])

        route = nx.shortest_path(G, orig_node, dest_node, weight='travel_time')
        route_nodes = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in route]

        route_length = sum(geodesic((G.nodes[route[i]]['y'], G.nodes[route[i]]['x']),
                                    (G.nodes[route[i+1]]['y'], G.nodes[route[i+1]]['x'])).meters
                           for i in range(len(route) - 1))
        route_time = sum(G.edges[route[i], route[i+1], 0].get('travel_time', 0)
                         for i in range(len(route) - 1)) / 60

        m = folium.Map(location=[user_lat, user_lon], zoom_start=14)
        folium.Marker((user_lat, user_lon), tooltip='You', popup='Your Location').add_to(m)
        folium.Marker(hosp_coords, tooltip=hospital_name,
                      popup=f"{hospital_name}<br>Distance: {route_length:.1f} m<br>Est. time: {route_time:.1f} mins",
                      icon=folium.Icon(color='red', icon='plus-sign')).add_to(m)
        folium.PolyLine(route_nodes, color="blue", weight=5, opacity=0.8).add_to(m)
        return m.get_root().render()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"<h3>Something went wrong:<br>{str(e)}</h3>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
