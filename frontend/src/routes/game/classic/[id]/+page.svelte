<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { getGame, submitOrders } from '$lib/api';
	import { connectToGame } from '$lib/websocket';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { GameState, Role, PlayerState } from '$lib/types';

	const ROLE_ORDER: Role[] = ['factory', 'distributor', 'wholesaler', 'retailer'];

	// Supply chain city positions [lon, lat]
	const CHAIN_CITIES: Record<string, { name: string; lon: number; lat: number; label: string }> = {
		factory:     { name: 'Eindhoven', lon: 5.4697,  lat: 51.4416, label: '🏭 Factory' },
		distributor: { name: 'Rotterdam', lon: 4.4777,  lat: 51.9244, label: '🚢 Distributor' },
		wholesaler:  { name: 'Amsterdam', lon: 4.9041,  lat: 52.3676, label: '🏪 Wholesaler' },
		retailer:    { name: 'Berlin',    lon: 13.4050, lat: 52.5200, label: '🛒 Retailer' },
		customer:    { name: 'London',    lon: -0.1278, lat: 51.5074, label: '👥 Customer' },
	};

	// Route lines: factory→distributor→wholesaler→retailer→customer
	const CHAIN_ROUTES = [
		['factory', 'distributor'],
		['distributor', 'wholesaler'],
		['wholesaler', 'retailer'],
		['retailer', 'customer'],
	];

	const ROLE_COLORS: Record<string, string> = {
		factory:     '#e74c3c',
		distributor: '#e67e22',
		wholesaler:  '#2980b9',
		retailer:    '#27ae60',
		customer:    '#8e44ad',
	};

	// ── State ──────────────────────────────────────────────────────────────────
	let gameId = $page.params.id;
	let state: GameState | null = null;
	let loadError = '';
	let submitError = '';
	let submitting = false;
	let cleanup: (() => void) | null = null;
	// Track the round number we last submitted for — re-enables form when round advances
	let lastSubmittedRound = -1;

	// MapLibre
	let mapContainer: HTMLElement;
	let map: maplibregl.Map | null = null;
	let mapLoaded = false;
	let nodeMarkers: Map<string, maplibregl.Marker> = new Map();

	// Order inputs for human roles
	let orderInputs: Record<string, string> = {};

	// ── Derived ────────────────────────────────────────────────────────────────
	$: humanRoles = state
		? ROLE_ORDER.filter((r) => state!.players[r]?.is_human)
		: [];

	// Classic game: round advances synchronously on submit.
	// Show form whenever the current round hasn't been submitted yet.
	$: canSubmit = state?.status === 'active'
		&& humanRoles.length > 0
		&& (state?.round ?? 0) >= lastSubmittedRound + 1;

	// ── Lifecycle ──────────────────────────────────────────────────────────────
	onMount(async () => {
		try {
			state = await getGame(gameId);
			initOrderInputs(state);
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Failed to load game.';
			return;
		}

		map = new maplibregl.Map({
			container: mapContainer,
			style: 'https://demotiles.maplibre.org/style.json',
			center: [6.5, 51.8],
			zoom: 4.6,
		});

		map.on('load', () => {
			mapLoaded = true;
			drawChain();
		});

		cleanup = connectToGame(gameId, (newState) => {
			state = newState;
			initOrderInputs(newState);
			if (mapLoaded) updateMarkers();
		});
	});

	onDestroy(() => {
		cleanup?.();
		map?.remove();
	});

	function initOrderInputs(s: GameState): void {
		for (const role of ROLE_ORDER) {
			if (s.players[role]?.is_human && !(role in orderInputs)) {
				orderInputs[role] = '4';
			}
		}
	}

	// ── Map ────────────────────────────────────────────────────────────────────

	function drawChain(): void {
		if (!map) return;

		// Draw route lines
		const routeFeatures: GeoJSON.Feature[] = CHAIN_ROUTES.map(([from, to]) => ({
			type: 'Feature',
			geometry: {
				type: 'LineString',
				coordinates: [
					[CHAIN_CITIES[from].lon, CHAIN_CITIES[from].lat],
					[CHAIN_CITIES[to].lon,   CHAIN_CITIES[to].lat],
				],
			},
			properties: {},
		}));

		map.addSource('chain-routes', {
			type: 'geojson',
			data: { type: 'FeatureCollection', features: routeFeatures },
		});

		map.addLayer({
			id: 'chain-routes-layer',
			type: 'line',
			source: 'chain-routes',
			paint: {
				'line-color': '#aaa',
				'line-width': 2,
				'line-dasharray': [6, 3],
				'line-opacity': 0.6,
			},
		});

		// Place city markers
		updateMarkers();
	}

	function updateMarkers(): void {
		if (!map) return;

		for (const role of ROLE_ORDER) {
			const city = CHAIN_CITIES[role];
			const player = state?.players[role];
			const color = ROLE_COLORS[role];
			const existing = nodeMarkers.get(role);

			const el = document.createElement('div');
			el.className = 'chain-node';
			el.style.setProperty('--node-color', color);
			if (player?.is_human) el.classList.add('is-human');

			el.innerHTML = `
				<div class="node-bubble">
					<div class="node-label">${city.label}</div>
					<div class="node-city">${city.name}</div>
					${player ? `
					<div class="node-stats">
						<span class="stat-inv">Inv: ${player.inventory}</span>
						<span class="stat-bl">BL: ${player.backlog}</span>
					</div>
					<div class="node-pipeline">
						▶ ${player.shipping_pipeline[0]} / ${player.shipping_pipeline[1]}
					</div>
					` : ''}
				</div>
			`;

			if (existing) {
				existing.remove();
				nodeMarkers.delete(role);
			}

			const marker = new maplibregl.Marker({ element: el })
				.setLngLat([city.lon, city.lat])
				.addTo(map!);
			nodeMarkers.set(role, marker);
		}

		// Customer node (static)
		if (!nodeMarkers.has('customer')) {
			const city = CHAIN_CITIES['customer'];
			const el = document.createElement('div');
			el.className = 'chain-node customer-node';
			el.style.setProperty('--node-color', ROLE_COLORS['customer']);
			el.innerHTML = `
				<div class="node-bubble">
					<div class="node-label">${city.label}</div>
					<div class="node-city">${city.name}</div>
					${state ? `<div class="node-pipeline">Demand: ${state.customer_demand}/round</div>` : ''}
				</div>
			`;
			const marker = new maplibregl.Marker({ element: el })
				.setLngLat([city.lon, city.lat])
				.addTo(map!);
			nodeMarkers.set('customer', marker);
		} else if (state) {
			// Update demand display
			const city = CHAIN_CITIES['customer'];
			const existing = nodeMarkers.get('customer');
			existing?.remove();
			nodeMarkers.delete('customer');
			const el = document.createElement('div');
			el.className = 'chain-node customer-node';
			el.style.setProperty('--node-color', ROLE_COLORS['customer']);
			el.innerHTML = `
				<div class="node-bubble">
					<div class="node-label">${city.label}</div>
					<div class="node-city">${city.name}</div>
					<div class="node-pipeline">Demand: ${state.customer_demand}/round</div>
				</div>
			`;
			const marker = new maplibregl.Marker({ element: el })
				.setLngLat([city.lon, city.lat])
				.addTo(map!);
			nodeMarkers.set('customer', marker);
		}
	}

	// ── Order submission ───────────────────────────────────────────────────────

	async function handleSubmit(): Promise<void> {
		if (!state || !canSubmit) return;
		submitError = '';
		submitting = true;

		const orders: Record<string, number> = {};
		for (const role of humanRoles) {
			const qty = parseInt(orderInputs[role] ?? '0', 10);
			if (isNaN(qty) || qty < 0) {
				submitError = `Invalid quantity for ${role}.`;
				submitting = false;
				return;
			}
			orders[role] = qty;
		}

		try {
			state = await submitOrders(gameId, orders);
			lastSubmittedRound = state.round;
			if (mapLoaded) updateMarkers();
		} catch (e) {
			submitError = e instanceof Error ? e.message : 'Failed to submit orders.';
		} finally {
			submitting = false;
		}
	}

	function fmt(n: number): string {
		return `$${n.toFixed(2)}`;
	}
</script>

<div class="layout">
	<!-- ── Map ──────────────────────────────────────────────────────────── -->
	<div class="map-area" bind:this={mapContainer}></div>

	<!-- ── Sidebar ──────────────────────────────────────────────────────── -->
	<aside class="sidebar">
		{#if loadError}
			<p class="error">{loadError}</p>
		{:else if !state}
			<p class="muted">Loading game...</p>
		{:else}
			<!-- Round header -->
			<div class="round-header">
				<span class="round-num">Round {state.round} / {state.max_rounds}</span>
				<span class="status-badge status-{state.status}">{state.status}</span>
			</div>

			<div class="demand-line">Customer demand: <strong>{state.customer_demand} units/round</strong></div>

			<!-- Chain summary table -->
			<div class="section-title">Supply Chain</div>
			<table class="chain-table">
				<thead>
					<tr>
						<th>Role</th>
						<th>Inv</th>
						<th>BL</th>
						<th>▶0</th>
						<th>▶1</th>
						<th>Cost</th>
					</tr>
				</thead>
				<tbody>
					{#each ROLE_ORDER as role}
						{@const p = state.players[role]}
						{#if p}
						<tr class:human-row={p.is_human}>
							<td class="role-cell" style="color:{ROLE_COLORS[role]}">{role}</td>
							<td>{p.inventory}</td>
							<td class:backlog-cell={p.backlog > 0}>{p.backlog}</td>
							<td>{p.shipping_pipeline[0]}</td>
							<td>{p.shipping_pipeline[1]}</td>
							<td class="cost-cell">{fmt(p.total_cost)}</td>
						</tr>
						{/if}
					{/each}
				</tbody>
			</table>

			<!-- Per-role detail for human roles -->
			{#each humanRoles as role}
				{@const p = state.players[role]}
				{#if p}
				<div class="my-station">
					<div class="section-title" style="color:{ROLE_COLORS[role]}">
						Your station — {role.charAt(0).toUpperCase() + role.slice(1)} ({CHAIN_CITIES[role]?.name})
					</div>
					<div class="stat-row">
						<span>Inventory</span><strong>{p.inventory}</strong>
					</div>
					<div class="stat-row">
						<span>Backlog</span><strong class:warn={p.backlog > 0}>{p.backlog}</strong>
					</div>
					<div class="stat-row">
						<span>Arrived this round</span><strong>{p.incoming_shipment}</strong>
					</div>
					<div class="stat-row">
						<span>Order received</span><strong>{p.incoming_order}</strong>
					</div>
					<div class="stat-row">
						<span>In transit (next)</span><strong>{p.shipping_pipeline[0]}</strong>
					</div>
					<div class="stat-row">
						<span>In transit (round+2)</span><strong>{p.shipping_pipeline[1]}</strong>
					</div>
					<div class="stat-row">
						<span>Cost this round</span><strong>{fmt(p.cost_this_round)}</strong>
					</div>
					<div class="stat-row">
						<span>Total cost</span><strong class="total-cost">{fmt(p.total_cost)}</strong>
					</div>
				</div>
				{/if}
			{/each}

			<!-- Order form -->
			{#if state.status === 'active'}
				<div class="section-title">Place Orders — Round {(state.round) + 1}</div>
				{#if canSubmit}
					{#each humanRoles as role}
						<div class="order-row">
							<label for="order-{role}">{role.charAt(0).toUpperCase() + role.slice(1)}</label>
							<input
								id="order-{role}"
								type="number"
								min="0"
								max="200"
								bind:value={orderInputs[role]}
							/>
							<span class="unit-label">units</span>
						</div>
					{/each}
					{#if submitError}<p class="error">{submitError}</p>{/if}
					<button class="btn-submit" onclick={handleSubmit} disabled={submitting || !canSubmit}>
						{submitting ? 'Submitting...' : '▶ Advance Round'}
					</button>
				{/if}
			{:else if state.status === 'complete'}
				<div class="game-over">
					<div class="section-title">Game Complete!</div>
					{#each ROLE_ORDER as role}
						{@const p = state.players[role]}
						{#if p}
						<div class="stat-row">
							<span>{role}</span>
							<strong class:warn={p.total_cost > 100}>{fmt(p.total_cost)}</strong>
						</div>
						{/if}
					{/each}
					<div class="stat-row total-row">
						<span>Team total</span>
						<strong>{fmt(ROLE_ORDER.reduce((s, r) => s + (state!.players[r]?.total_cost ?? 0), 0))}</strong>
					</div>
					<a href="/" class="btn-submit" style="display:block;text-align:center;margin-top:1rem;text-decoration:none;">
						Play Again
					</a>
				</div>
			{/if}
		{/if}
	</aside>
</div>

<style>
	:global(body) { margin: 0; padding: 0; }

	.layout {
		display: grid;
		grid-template-columns: 65% 35%;
		height: 100vh;
		overflow: hidden;
		font-family: system-ui, sans-serif;
	}

	.map-area {
		width: 100%;
		height: 100%;
	}

	.sidebar {
		background: #1a1a2e;
		color: #e0e0e0;
		overflow-y: auto;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		font-size: 0.88rem;
	}

	.round-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.round-num {
		font-size: 1.1rem;
		font-weight: 700;
		color: #c8a227;
	}

	.status-badge {
		font-size: 0.7rem;
		padding: 0.2rem 0.5rem;
		border-radius: 4px;
		font-weight: 700;
		text-transform: uppercase;
	}
	.status-active  { background: #27ae60; color: #fff; }
	.status-complete { background: #e74c3c; color: #fff; }
	.status-waiting { background: #888; color: #fff; }

	.demand-line { font-size: 0.82rem; color: #aaa; }

	.section-title {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #888;
		border-bottom: 1px solid #333;
		padding-bottom: 0.25rem;
		margin-top: 0.25rem;
	}

	.chain-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8rem;
	}
	.chain-table th {
		text-align: left;
		color: #666;
		font-weight: 600;
		padding: 0.2rem 0.3rem;
	}
	.chain-table td {
		padding: 0.2rem 0.3rem;
		border-top: 1px solid #222;
	}
	.human-row td { background: #1e2a3a; }
	.role-cell { font-weight: 700; }
	.backlog-cell { color: #e74c3c; font-weight: 700; }
	.cost-cell { color: #e67e22; }

	.my-station {
		background: #16213e;
		border-radius: 6px;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}

	.stat-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.85rem;
	}
	.stat-row span { color: #aaa; }
	.stat-row strong { color: #e0e0e0; }
	.warn { color: #e74c3c !important; }
	.total-cost { color: #e67e22 !important; }

	.order-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.order-row label {
		width: 90px;
		font-size: 0.85rem;
		color: #ccc;
	}
	.order-row input {
		width: 70px;
		padding: 0.35rem 0.5rem;
		background: #2a2a4e;
		border: 1px solid #444;
		border-radius: 4px;
		color: #fff;
		font-size: 0.9rem;
	}
	.unit-label { color: #666; font-size: 0.8rem; }

	.btn-submit {
		width: 100%;
		padding: 0.65rem;
		background: #e67e22;
		color: #fff;
		border: none;
		border-radius: 6px;
		font-size: 0.95rem;
		font-weight: 700;
		cursor: pointer;
		margin-top: 0.5rem;
	}
	.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }
	.btn-submit:hover:not(:disabled) { background: #cf6d17; }

	.waiting {
		color: #888;
		font-size: 0.85rem;
		text-align: center;
		padding: 0.75rem;
		background: #111;
		border-radius: 4px;
		margin: 0;
	}

	.game-over .total-row {
		border-top: 1px solid #444;
		padding-top: 0.4rem;
		margin-top: 0.4rem;
		font-weight: 700;
		font-size: 0.95rem;
	}

	.error { color: #e74c3c; font-size: 0.85rem; margin: 0; }
	.muted { color: #666; font-size: 0.85rem; }

	/* ── Map markers ── */
	:global(.chain-node) {
		cursor: pointer;
	}

	:global(.node-bubble) {
		background: var(--node-color, #444);
		color: #fff;
		border-radius: 8px;
		padding: 0.4rem 0.6rem;
		font-size: 0.72rem;
		white-space: nowrap;
		box-shadow: 0 2px 8px rgba(0,0,0,0.4);
		border: 2px solid rgba(255,255,255,0.2);
		min-width: 90px;
	}

	:global(.is-human .node-bubble) {
		border: 2px solid #fff;
		box-shadow: 0 0 0 3px rgba(255,255,255,0.3), 0 2px 8px rgba(0,0,0,0.4);
	}

	:global(.node-label) {
		font-weight: 700;
		font-size: 0.75rem;
	}

	:global(.node-city) {
		opacity: 0.8;
		font-size: 0.68rem;
	}

	:global(.node-stats) {
		display: flex;
		gap: 0.4rem;
		margin-top: 0.2rem;
		font-size: 0.7rem;
	}

	:global(.stat-inv) { color: #90EE90; }
	:global(.stat-bl)  { color: #FFB6C1; }

	:global(.node-pipeline) {
		margin-top: 0.15rem;
		font-size: 0.65rem;
		opacity: 0.85;
	}
</style>
