/**
 * MapLibre GL initialization and helpers for Logistics Wars.
 *
 * Provides:
 *  - initMap()           — boot a MapLibre map centred on Europe
 *  - addCityMarker()     — place a coloured DOM marker for a supply-chain city
 *  - drawShipmentLine()  — draw / update a route line + animated dot for a shipment
 *  - removeShipmentLine()— tear down a shipment's layers and source
 */

import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

// ── Public types ────────────────────────────────────────────────────────────

export type CityMarker = {
	city_id: string;
	name: string;
	lat: number;
	lon: number;
	role: string;
};

export type ShipmentLine = {
	shipment_id: string;
	from: [number, number]; // [lon, lat]
	to: [number, number];
	mode: 'truck' | 'train' | 'ship';
	progress: number; // 0.0 – 1.0
};

// ── Colour palette ──────────────────────────────────────────────────────────

const MODE_COLORS: Record<string, string> = {
	truck: '#e67e22',
	train: '#2980b9',
	ship: '#27ae60',
};

// ── Map initialisation ──────────────────────────────────────────────────────

/**
 * Create and return a MapLibre Map instance mounted on `container`.
 * Centred on Central Europe at zoom 4.5.
 */
export function initMap(container: HTMLElement): maplibregl.Map {
	return new maplibregl.Map({
		container,
		style: 'https://demotiles.maplibre.org/style.json',
		center: [8, 51],
		zoom: 4.5,
	});
}

// ── City markers ────────────────────────────────────────────────────────────

/**
 * Add a coloured DOM marker for `city` and attach a popup with the city name.
 * Returns the Marker instance so the caller can remove it later.
 */
export function addCityMarker(
	map: maplibregl.Map,
	city: CityMarker,
	isPlayerCity: boolean,
): maplibregl.Marker {
	const el = document.createElement('div');
	el.className = `city-marker ${city.role} ${isPlayerCity ? 'player-city' : ''}`;
	el.title = city.name;

	return new maplibregl.Marker({ element: el })
		.setLngLat([city.lon, city.lat])
		.setPopup(new maplibregl.Popup({ offset: 25 }).setText(city.name))
		.addTo(map);
}

// ── Shipment lines ───────────────────────────────────────────────────────────

/**
 * Draw or update a shipment route line and moving dot.
 *
 * First call: adds GeoJSON source + two layers (line + dot).
 * Subsequent calls: updates the source data to move the dot.
 */
export function drawShipmentLine(map: maplibregl.Map, shipment: ShipmentLine): void {
	const sourceId = `shipment-${shipment.shipment_id}`;
	const layerId = `shipment-layer-${shipment.shipment_id}`;

	// Current interpolated position
	const lon = shipment.from[0] + (shipment.to[0] - shipment.from[0]) * shipment.progress;
	const lat = shipment.from[1] + (shipment.to[1] - shipment.from[1]) * shipment.progress;
	const color = MODE_COLORS[shipment.mode] ?? '#888';

	const geojson: GeoJSON.FeatureCollection = {
		type: 'FeatureCollection',
		features: [
			{
				type: 'Feature',
				geometry: { type: 'LineString', coordinates: [shipment.from, shipment.to] },
				properties: { mode: shipment.mode },
			},
			{
				type: 'Feature',
				geometry: { type: 'Point', coordinates: [lon, lat] },
				properties: { mode: shipment.mode },
			},
		],
	};

	if (!map.getSource(sourceId)) {
		map.addSource(sourceId, { type: 'geojson', data: geojson });

		map.addLayer({
			id: `${layerId}-line`,
			type: 'line',
			source: sourceId,
			filter: ['==', ['geometry-type'], 'LineString'],
			paint: {
				'line-color': color,
				'line-width': 2,
				'line-dasharray': [4, 4],
				'line-opacity': 0.6,
			},
		});

		map.addLayer({
			id: `${layerId}-dot`,
			type: 'circle',
			source: sourceId,
			filter: ['==', ['geometry-type'], 'Point'],
			paint: {
				'circle-radius': 6,
				'circle-color': color,
				'circle-stroke-width': 2,
				'circle-stroke-color': '#fff',
			},
		});
	} else {
		(map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geojson);
	}
}

// ── Route lines ──────────────────────────────────────────────────────────────

export type RouteMode = {
	mode: string;
	transit_minutes: number;
	cost_per_unit: number;
	min_quantity: number;
};

export type Route = {
	from_city: string;
	to_city: string;
	modes: RouteMode[];
};

export type City = {
	city_id: string;
	name: string;
	lat: number;
	lon: number;
	available_roles: string[];
};

/**
 * Draw static background route lines for each transport mode.
 * Safe to call multiple times — skips sources that already exist.
 */
export function drawRouteLines(
	map: maplibregl.Map,
	routes: Route[],
	cities: Record<string, City>,
): void {
	const ROUTE_COLORS: Record<string, string> = {
		truck: '#e67e22', train: '#2980b9', ship: '#27ae60',
	};
	const byMode: Record<string, GeoJSON.Feature[]> = { truck: [], train: [], ship: [] };
	for (const route of routes) {
		const fromCity = cities[route.from_city];
		const toCity = cities[route.to_city];
		if (!fromCity || !toCity) continue;
		for (const rm of route.modes) {
			byMode[rm.mode]?.push({
				type: 'Feature',
				geometry: { type: 'LineString', coordinates: [[fromCity.lon, fromCity.lat], [toCity.lon, toCity.lat]] },
				properties: { mode: rm.mode },
			});
		}
	}
	for (const [mode, features] of Object.entries(byMode)) {
		const sourceId = `routes-${mode}`;
		if (map.getSource(sourceId)) continue;
		map.addSource(sourceId, { type: 'geojson', data: { type: 'FeatureCollection', features } });
		map.addLayer({
			id: `routes-layer-${mode}`,
			type: 'line',
			source: sourceId,
			paint: {
				'line-color': ROUTE_COLORS[mode] ?? '#888',
				'line-width': 1.5,
				'line-opacity': 0.35,
				'line-dasharray': [4, 4],
			},
		});
	}
}

/**
 * Remove all layers and the GeoJSON source for a shipment.
 * Safe to call even if the shipment was never drawn.
 */
export function removeShipmentLine(map: maplibregl.Map, shipmentId: string): void {
	const sourceId = `shipment-${shipmentId}`;
	const layerId = `shipment-layer-${shipmentId}`;

	if (map.getLayer(`${layerId}-dot`)) map.removeLayer(`${layerId}-dot`);
	if (map.getLayer(`${layerId}-line`)) map.removeLayer(`${layerId}-line`);
	if (map.getSource(sourceId)) map.removeSource(sourceId);
}
