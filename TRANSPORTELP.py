import json
import urllib.request
import urllib.error

# Base URL de la API de transporte de la Municipalidad de La Plata
BASE_URL = "https://www.laplata.gob.ar:8080/web-central/api/public/transporte"

def get_json(url):
    """Realiza una petición HTTP GET y retorna el JSON parsed."""
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def extraer_transporte_geojson():
    geojson_out = {
        "type": "FeatureCollection",
        "features": []
    }
    
    # 1. Obtener todas las líneas disponibles
    url_lineas = f"{BASE_URL}/obtenerLineas?page=0"
    print(f"Obteniendo lista de líneas desde {url_lineas}...")
    try:
        lineas = get_json(url_lineas)
    except Exception as e:
        print(f"Error al obtener las líneas: {e}")
        return

    print(f"Se encontraron {len(lineas)} líneas.")

    # Iterate over lines
    for linea in lineas:
        linea_id = linea.get("id")
        linea_nombre = linea.get("nombre", "")
        linea_color = linea.get("color", "#3388ff") # Color institucional por defecto
        
        # 2. Obtener los ramales de cada línea
        url_ramales = f"{BASE_URL}/obtenerRamalesPorLinea?idLinea={linea_id}"
        try:
            ramales = get_json(url_ramales)
        except Exception as e:
            print(f"Error al obtener ramales de la línea {linea_nombre} (ID: {linea_id}): {e}")
            continue

        for ramal in ramales:
            ramal_id = ramal.get("id")
            ramal_nombre = ramal.get("nombre", "")
            
            # 3. Obtener el detalle del ramal (recorrido y paradas)
            url_detalle = f"{BASE_URL}/obtenerRamal?idRamal={ramal_id}"
            try:
                detalle = get_json(url_detalle)
            except Exception as e:
                print(f"Error al obtener detalle del ramal {ramal_nombre} (ID: {ramal_id}): {e}")
                continue

            descripcion = detalle.get("descripcion", "")
            
            # Crear mapa de paradas (codigo -> nombre) para cruzar datos
            paradas_info = {}
            for p in detalle.get("paradas", []):
                paradas_info[p.get("codigo")] = p.get("nombre")

            # Parsear el tramoJson con las geometrías GeoJSON
            tramo_raw = detalle.get("tramoJson")
            if tramo_raw:
                try:
                    tramo_data = json.loads(tramo_raw)
                    features = tramo_data.get("features", [])
                    
                    for feat in features:
                        geom = feat.get("geometry", {})
                        props = feat.get("properties", {})
                        
                        # Inyectar metadatos útiles para uMap
                        props["linea"] = linea_nombre
                        props["ramal"] = ramal_nombre
                        props["descripcion"] = descripcion
                        
                        # Estilos compatibles con uMap / Leaflet
                        props["stroke"] = linea_color
                        props["stroke-width"] = 4
                        props["stroke-opacity"] = 0.8
                        props["fill"] = linea_color

                        if geom.get("type") == "Point":
                            codigo = props.get("codigo")
                            nombre_parada = paradas_info.get(codigo, props.get("label", ""))
                            props["name"] = f"Parada: {nombre_parada}"
                            props["tipo"] = "Parada"
                        elif geom.get("type") in ["LineString", "MultiLineString"]:
                            props["name"] = f"Línea {linea_nombre} - {ramal_nombre}"
                            props["tipo"] = "Recorrido"
                            
                        feature_obj = {
                            "type": "Feature",
                            "geometry": geom,
                            "properties": props
                        }
                        geojson_out["features"].append(feature_obj)
                        
                except json.JSONDecodeError:
                    print(f"No se pudo parsear `tramoJson` para el ramal ID {ramal_id}")

    # 4. Guardar archivo listo para importar en uMap
    output_filename = "transporte_la_plata.geojson"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(geojson_out, f, ensure_ascii=False, indent=2)
    
    print(f"\n¡Proceso finalizado! Se guardó el archivo '{output_filename}'.")

if __name__ == "__main__":
    extraer_transporte_geojson()