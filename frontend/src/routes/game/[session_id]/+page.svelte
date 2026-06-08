<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { getSession, placeOrder, getMapData, startSession } from '$lib/api';
	import { connectToSession } from '$lib/websocket';
	import maplibregl from 'maplibre-gl';
	import { initMap, addCityMarker, drawShipmentLine, removeShipmentLine, drawRouteLines } from '$lib/map';
	import type {
		GameSession,
		Company,
		Shipment,
		TransportMode,
		City,
		MapData,
	} from '$lib/types';

	// ── Route param ────────────────────────────────────────────────────────────
	let sessionId = $page.params.session_id;

	// ── State ──────────────────────────────────────────────────────────────────
	let session: GameSession | null = null;
	let mapData: MapData | null = null;
	let loadError = '';

	// The company_id that belongs to this browser session (set after join)
	// Stored in sessionStorage so it survives page refreshes.
	let myCompanyId: string = '';

	// MapLibre
	let mapContainer: HTMLElement;
	let map: maplibregl.Map | null = null;
	let mapLoaded = false;
	let cityMarkers: Map<string, maplibregl.Marker> = new Map();
	let drawnShipments: Set<string> = new Set();

	// Order form
	let orderSellerId = '';
	let orderQty = 10;
	let orderMode: TransportMode = 'truck';
	let orderLoading = false;
	let orderError = '';
	let orderSuccess = '';

	// Cleanup
	let wsCleanup: (() => void) | null = null;
	let animationInterval: ReturnType<typeof setInterval> | null = null;

	// ── Derived helpers ────────────────────────────────────────────────────────
	$: myCompany = session && myCompanyId ? session.companies[myCompanyId] ?? null : null;

	$: upstreamRole = myCompany && mapData ? (mapData.upstream_role[myCompany.role] ?? null) : null;

	$: suppliers = session && upstreamRole
		? Object.values(session.companies).filter((c) => c.role === upstreamRole)
		: [];

	$: otherCompanies = session
		? Object.values(session.companies).filter((c) => c.company_id !== myCompanyId)
		: [];

	$: activeShipments = session
		? Object.values(session.shipments).filter((s) => s.status === 'in_transit')
		: [];

	$: if (mapLoaded && mapData && map) { drawRouteLines(map, mapData.routes, mapData.cities); }

	$: availableModes = (() => {
		if (!orderSellerId || !myCompany || !mapData) return ['truck', 'train', 'ship'] as string[];
		const seller = session?.companies[orderSellerId];
		if (!seller) return ['truck', 'train', 'ship'] as string[];
		const route = mapData.routes.find(r =>
			(r.from_city === seller.city_id && r.to_city === myCompany!.city_id) ||
			(r.from_city === myCompany!.city_id && r.to_city === seller.city_id)
		);
		return route ? route.modes.map(m => m.mode) : [];
	})();

	$: myActiveShipments = activeShipments.filter(
		(s) => s.from_company_id === myCompanyId || s.to_company_id === myCompanyId,
	);

	$: liveLeaderboard = session
		? Object.values(session.companies)
			.map((c) => ({ ...c, profit: c.total_revenue - c.total_costs }))
			.sort((a, b) => b.profit - a.profit)
		: [];

	$: myRecentOrders = session
		? Object.values(session.shipments)
			.filter((s) => s.to_company_id === myCompanyId)
			.sort((a, b) => b.departs_at - a.departs_at)
			.slice(0, 5)
		: [];

	$: timeRemaining = session && session.ends_at > 0
		? Math.max(0, Math.floor(session.ends_at - Date.now() / 1000))
		: 0;

	function formatTime(secs: number): string {
		const m = Math.floor(secs / 60);
		const s = secs % 60;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function profitLoss(c: Company): number {
		return c.total_revenue - c.total_costs;
	}

	function shipmentEta(s: Shipment): number {
		return Math.max(0, Math.floor(s.arrives_at - Date.now() / 1000));
	}

	function cityName(cityId: string): string {
		return mapData?.cities[cityId]?.name ?? cityId;
	}

	// ── Map helpers ────────────────────────────────────────────────────────────

	function syncMapMarkers(): void {
		if (!map || !mapData || !session) return;

		// Add markers for cities that have a company in this session
		for (const company of Object.values(session.companies)) {
			const city = mapData.cities[company.city_id];
			if (!city || cityMarkers.has(city.city_id)) continue;

			const marker = addCityMarker(
				map,
				{ city_id: city.city_id, name: city.name, lat: city.lat, lon: city.lon, role: company.role },
				company.company_id === myCompanyId,
			);
			cityMarkers.set(city.city_id, marker);
		}
	}

	function updateShipments(): void {
		if (!map || !session || !mapData) return;

		const now = Date.now() / 1000;
		const activeIds = new Set<string>();

		for (const shipment of activeShipments) {
			activeIds.add(shipment.shipment_id);
			const fromCity = mapData.cities[
				session.companies[shipment.from_company_id]?.city_id ?? ''
			];
			const toCity = mapData.cities[
				session.companies[shipment.to_company_id]?.city_id ?? ''
			];
			if (!fromCity || !toCity) continue;

			const duration = shipment.arrives_at - shipment.departs_at;
			const elapsed = now - shipment.departs_at;
			const progress = duration > 0 ? Math.min(1, Math.max(0, elapsed / duration)) : 0;

			drawShipmentLine(map, {
				shipment_id: shipment.shipment_id,
				from: [fromCity.lon, fromCity.lat],
				to: [toCity.lon, toCity.lat],
				mode: shipment.transport_mode,
				progress,
			});
			drawnShipments.add(shipment.shipment_id);
		}

		// Remove lines for shipments that are no longer in_transit
		for (const id of [...drawnShipments]) {
			if (!activeIds.has(id)) {
				removeShipmentLine(map, id);
				drawnShipments.delete(id);
			}
		}
	}

	// ── Lifecycle ──────────────────────────────────────────────────────────────

	onMount(async () => {
		// Retrieve own company_id from sessionStorage
		myCompanyId = sessionStorage.getItem(`lw_company_${sessionId}`) ?? '';

		// Load session + map data in parallel
		try {
			[session, mapData] = await Promise.all([getSession(sessionId), getMapData()]);
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Failed to load session.';
			return;
		}

		// Boot map after DOM is ready
		map = initMap(mapContainer);

		map.on('load', () => {
			mapLoaded = true;
			if (mapData) drawRouteLines(map!, mapData.routes, mapData.cities);
			syncMapMarkers();
			updateShipments();
		});

		// Subscribe to live updates
		wsCleanup = connectToSession(sessionId, (updatedSession) => {
			session = updatedSession;
			syncMapMarkers();
			updateShipments();
		});

		// Animate shipment dots every 2 seconds
		animationInterval = setInterval(() => {
			updateShipments();
		}, 2000);
	});

	onDestroy(() => {
		wsCleanup?.();
		if (animationInterval !== null) clearInterval(animationInterval);
		map?.remove();
	});

	// ── Order placement ────────────────────────────────────────────────────────

	async function handlePlaceOrder(): Promise<void> {
		if (!myCompanyId) { orderError = 'No company linked to this browser session.'; return; }
		if (!orderSellerId) { orderError = 'Choose a supplier.'; return; }
		if (orderQty < 1) { orderError = 'Quantity must be at least 1.'; return; }

		orderLoading = true;
		orderError = '';
		orderSuccess = '';

		try {
			const result = await placeOrder(sessionId, myCompanyId, orderSellerId, orderQty, orderMode);
			session = result.session;
			orderSuccess = `Shipment dispatched! ETA: ${formatTime(shipmentEta(result.shipment))}`;
			orderSellerId = '';
			orderQty = 10;
		} catch (e) {
			orderError = e instanceof Error ? e.message : 'Order failed.';
		} finally {
			orderLoading = false;
		}
	}

	async function handleStartSession(): Promise<void> {
		try {
			session = await startSession(sessionId);
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Failed to start session.';
		}
	}
</script>

{#if loadError}
	<div class="error-banner">{loadError}</div>
{:else if !session}
	<p class="loading">Loading session...</p>
{:else}
	<div class="game-layout">
		<!-- ── Map ──────────────────────────────────────────────────────────── -->
		<div class="map-container">
			<div bind:this={mapContainer} class="map-el"></div>

			<!-- Map legend overlay -->
			<div class="map-legend">
				<span class="legend-dot truck"></span> Truck
				<span class="legend-dot train"></span> Train
				<span class="legend-dot ship"></span> Ship
			</div>
		</div>

		<!-- ── Sidebar ──────────────────────────────────────────────────────── -->
		<aside class="sidebar">
			<!-- Session header -->
			<div class="sidebar-header">
				<div class="room-code">Room: <strong>{session.room_code}</strong></div>
				<div class="time-remaining" class:urgent={timeRemaining < 120}>
					{#if session.status === 'active'}
						{formatTime(timeRemaining)} remaining
					{:else if session.status === 'lobby'}
						Waiting for players
					{:else}
						Game over
					{/if}
				</div>
			</div>

			<!-- Lobby: start button -->
			{#if session.status === 'lobby'}
				<div class="lobby-notice">
					<p style="font-size:0.8rem;color:#aaa;margin:0 0 0.25rem">Share with other players:</p>
					<div class="room-code-display">{session.room_code}</div>
					<p style="font-size:0.75rem;color:#888;margin:0.4rem 0 0.75rem">
						{Object.keys(session.companies).length} player(s) in lobby
					</p>
					<button class="btn-primary" onclick={handleStartSession}>▶ Start Game</button>
				</div>
			{/if}

			<!-- My company dashboard -->
			{#if myCompany}
				<div class="company-card my-card">
					<div class="company-name">{myCompany.player_name}</div>
					<div class="company-meta">{myCompany.role} &mdash; {cityName(myCompany.city_id)}</div>

					<div class="cash" class:cash-warn={myCompany.cash < 1000}>
						${myCompany.cash.toLocaleString()}
					</div>

					<div class="stat-row">
						<span class="stat-label">Inventory</span>
						<div class="inventory-bar-wrap">
							<div
								class="inventory-bar"
								style="width: {Math.min(100, (myCompany.inventory / 200) * 100)}%"
							></div>
						</div>
						<span class="stat-val">{myCompany.inventory}</span>
					</div>

					<div class="stat-row">
						<span class="stat-label">Backlog</span>
						<span class="stat-val" class:warn={myCompany.backlog > 0}>{myCompany.backlog}</span>
					</div>

					<div class="stat-row">
						<span class="stat-label">P&amp;L</span>
						<span
							class="stat-val"
							class:profit={profitLoss(myCompany) >= 0}
							class:loss={profitLoss(myCompany) < 0}
						>
							${profitLoss(myCompany).toLocaleString()}
						</span>
					</div>

					{#if myCompany.is_bankrupt}
						<div class="bankrupt-badge">BANKRUPT</div>
					{/if}
				</div>
			{/if}

			<!-- Other companies -->
			{#if otherCompanies.length > 0}
				<div class="section-title">Other players</div>
				{#each otherCompanies as company}
					<div class="company-card" class:bankrupt={company.is_bankrupt}>
						<div class="company-name">{company.player_name}</div>
						<div class="company-meta">{company.role} &mdash; {cityName(company.city_id)}</div>
						<div class="stat-row">
							<span class="stat-label">Cash</span>
							<span class="stat-val">${company.cash.toLocaleString()}</span>
						</div>
						<div class="stat-row">
							<span class="stat-label">Inv</span>
							<span class="stat-val">{company.inventory}</span>
						</div>
					</div>
				{/each}
			{/if}

			<!-- Live leaderboard (active game only) -->
			{#if session.status === 'active' && liveLeaderboard.length > 0}
				<div class="section-title">Standings</div>
				<div class="live-leaderboard">
					{#each liveLeaderboard as c, i}
						<div
							class="lb-row"
							class:lb-mine={c.company_id === myCompanyId}
							class:lb-bankrupt={c.is_bankrupt}
						>
							<span class="lb-rank">#{i + 1}</span>
							<span class="lb-name">{c.player_name}</span>
							<span class:profit={c.profit >= 0} class:loss={c.profit < 0}>
								${c.profit.toLocaleString(undefined, { maximumFractionDigits: 0 })}
							</span>
						</div>
					{/each}
				</div>
			{/if}

			<!-- Active shipments list -->
			{#if myActiveShipments.length > 0}
				<div class="section-title">Active shipments</div>
				<div class="shipment-list">
					{#each myActiveShipments as s}
						<div class="shipment-item">
							<span class="shipment-mode mode-{s.transport_mode}">{s.transport_mode}</span>
							<span>{cityName(s.from_city)} &rarr; {cityName(s.to_city)}</span>
							<span class="shipment-qty">{s.quantity} units</span>
							<span class="shipment-eta">ETA {formatTime(shipmentEta(s))}</span>
						</div>
					{/each}
				</div>
			{/if}

			<!-- Order history (my received shipments) -->
			{#if myRecentOrders.length > 0}
				<div class="section-title">Order history</div>
				<div class="order-history">
					{#each myRecentOrders as s}
						<div class="oh-row" class:oh-delivered={s.status === 'delivered'}>
							<span class="shipment-mode mode-{s.transport_mode}">{s.transport_mode}</span>
							<span class="oh-route">{cityName(s.from_city)} &rarr; {cityName(s.to_city)}</span>
							<span class="oh-qty">{s.quantity}u</span>
							<span class="oh-status status-{s.status}">{s.status}</span>
							<span class="oh-cost">-${s.shipping_cost.toFixed(0)}</span>
						</div>
					{/each}
				</div>
			{/if}

			<!-- Order form (only when active and not bankrupt) -->
			{#if session.status === 'active' && myCompany && !myCompany.is_bankrupt}
				<div class="section-title">Place order</div>
				<div class="order-form">
					<div class="form-group">
						<label for="order-seller">Supplier</label>
						<select id="order-seller" bind:value={orderSellerId}>
							<option value="">— choose supplier —</option>
							{#each suppliers as c}
								<option value={c.company_id}>{c.player_name} · {c.city_id} · {c.inventory} units</option>
							{/each}
						</select>
						{#if suppliers.length === 0}
							<p class="muted" style="font-size:0.8rem;margin-top:4px">No upstream supplier in session yet.</p>
						{/if}
					</div>

					<div class="form-row">
						<div class="form-group form-group--inline">
							<label for="order-qty">Qty</label>
							<input id="order-qty" type="number" min="1" bind:value={orderQty} />
						</div>
						<div class="form-group form-group--inline">
							<label for="order-mode">Mode</label>
							<select id="order-mode" bind:value={orderMode}>
								{#each availableModes as mode}
									<option value={mode}>{mode.charAt(0).toUpperCase() + mode.slice(1)}</option>
								{/each}
							</select>
						</div>
					</div>

					{#if orderError}<p class="error">{orderError}</p>{/if}
					{#if orderSuccess}<p class="success">{orderSuccess}</p>{/if}

					<button class="btn-ship" onclick={handlePlaceOrder} disabled={orderLoading}>
						{orderLoading ? 'Dispatching...' : 'Ship It'}
					</button>
				</div>
			{/if}

			<!-- Game over -->
			{#if session.status === 'complete'}
				<div class="section-title">Final standings</div>
				{#each Object.values(session.companies).sort((a, b) => profitLoss(b) - profitLoss(a)) as c, i}
					<div class="leaderboard-row">
						<span class="rank">#{i + 1}</span>
						<span>{c.player_name}</span>
						<span class:profit={profitLoss(c) >= 0} class:loss={profitLoss(c) < 0}>
							${profitLoss(c).toLocaleString()}
						</span>
					</div>
				{/each}
				<a href="/" class="btn-secondary">New game</a>
			{/if}
		</aside>
	</div>
{/if}

<style>
	/* ── Layout ─────────────────────────────────────────────────────────────── */
	.game-layout {
		display: grid;
		grid-template-columns: 1fr 320px;
		height: 100vh;
		overflow: hidden;
	}

	.map-container {
		position: relative;
	}

	.map-el {
		width: 100%;
		height: 100%;
	}

	/* ── Map legend ─────────────────────────────────────────────────────────── */
	.map-legend {
		position: absolute;
		bottom: 1rem;
		left: 1rem;
		background: rgba(255, 255, 255, 0.9);
		border-radius: 6px;
		padding: 0.4rem 0.75rem;
		font-size: 0.8rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		pointer-events: none;
		box-shadow: 0 1px 4px rgba(0,0,0,0.2);
	}

	.legend-dot {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 50%;
	}
	.legend-dot.truck { background: #e67e22; }
	.legend-dot.train { background: #2980b9; }
	.legend-dot.ship  { background: #27ae60; }

	/* ── Sidebar ────────────────────────────────────────────────────────────── */
	.sidebar {
		overflow-y: auto;
		padding: 1rem;
		background: #1a1a2e;
		color: #eee;
		font-family: system-ui, sans-serif;
		font-size: 0.88rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.sidebar-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		border-bottom: 1px solid #2e2e4e;
		padding-bottom: 0.5rem;
	}

	.room-code {
		font-size: 0.85rem;
		color: #aaa;
	}

	.time-remaining {
		font-size: 0.95rem;
		font-weight: 700;
		color: #7ec8e3;
	}

	.time-remaining.urgent {
		color: #e74c3c;
		animation: pulse 1s infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	/* ── Lobby notice ───────────────────────────────────────────────────────── */
	.lobby-notice {
		background: #252545;
		border-radius: 6px;
		padding: 0.75rem;
		text-align: center;
	}

	.lobby-notice p {
		margin: 0 0 0.5rem;
		font-size: 0.85rem;
		color: #ccc;
	}

	.room-code-display {
		font-size: 2rem;
		font-weight: 800;
		letter-spacing: 0.25em;
		color: #f0c040;
		background: #111128;
		border-radius: 6px;
		padding: 0.5rem;
		user-select: all;
		cursor: pointer;
	}

	/* ── Company cards ──────────────────────────────────────────────────────── */
	.company-card {
		background: #252545;
		border-radius: 8px;
		padding: 0.75rem;
	}

	.my-card {
		border: 1px solid #7ec8e3;
	}

	.company-card.bankrupt {
		opacity: 0.5;
	}

	.company-name {
		font-weight: 700;
		font-size: 0.95rem;
		margin-bottom: 0.1rem;
	}

	.company-meta {
		font-size: 0.75rem;
		color: #aaa;
		margin-bottom: 0.5rem;
		text-transform: capitalize;
	}

	.cash {
		font-size: 1.6rem;
		font-weight: 800;
		color: #7ec8e3;
		margin-bottom: 0.5rem;
	}

	.cash.cash-warn {
		color: #e74c3c;
	}

	.stat-row {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-bottom: 0.25rem;
	}

	.stat-label {
		color: #888;
		min-width: 55px;
		font-size: 0.8rem;
	}

	.stat-val {
		font-weight: 600;
		margin-left: auto;
	}

	.stat-val.warn { color: #e74c3c; }
	.stat-val.profit { color: #2ecc71; }
	.stat-val.loss { color: #e74c3c; }
	.profit { color: #2ecc71; }
	.loss { color: #e74c3c; }

	.inventory-bar-wrap {
		flex: 1;
		height: 6px;
		background: #3a3a5e;
		border-radius: 3px;
		overflow: hidden;
	}

	.inventory-bar {
		height: 100%;
		background: #7ec8e3;
		border-radius: 3px;
		transition: width 0.4s ease;
	}

	.bankrupt-badge {
		margin-top: 0.5rem;
		background: #c0392b;
		color: #fff;
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-align: center;
		border-radius: 4px;
		padding: 0.2rem 0.4rem;
	}

	/* ── Section titles ─────────────────────────────────────────────────────── */
	.section-title {
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: #666;
		border-top: 1px solid #2e2e4e;
		padding-top: 0.5rem;
	}

	/* ── Shipment list ──────────────────────────────────────────────────────── */
	.shipment-list {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.shipment-item {
		background: #252545;
		border-radius: 5px;
		padding: 0.4rem 0.6rem;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.8rem;
		flex-wrap: wrap;
	}

	.shipment-mode {
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		border-radius: 3px;
		padding: 0.1rem 0.3rem;
	}

	.mode-truck { background: #e67e22; color: #fff; }
	.mode-train { background: #2980b9; color: #fff; }
	.mode-ship  { background: #27ae60; color: #fff; }

	.shipment-qty { margin-left: auto; color: #aaa; }
	.shipment-eta { color: #7ec8e3; font-size: 0.78rem; }

	/* ── Order form ─────────────────────────────────────────────────────────── */
	.order-form {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.form-group label {
		font-size: 0.78rem;
		color: #aaa;
	}

	.form-group select,
	.form-group input {
		background: #252545;
		border: 1px solid #3a3a5e;
		color: #eee;
		border-radius: 4px;
		padding: 0.35rem 0.5rem;
		font-size: 0.88rem;
	}

	.form-group select option {
		background: #1a1a2e;
	}

	.form-row {
		display: flex;
		gap: 0.5rem;
	}

	.form-group--inline {
		flex: 1;
	}

	.btn-ship {
		background: #c8a227;
		color: #fff;
		border: none;
		border-radius: 6px;
		padding: 0.55rem 1rem;
		font-size: 0.9rem;
		font-weight: 700;
		cursor: pointer;
		transition: background 0.15s;
		width: 100%;
	}

	.btn-ship:hover:not(:disabled) {
		background: #a8841f;
	}

	.btn-ship:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	/* ── Live leaderboard (in-game) ────────────────────────────────────────── */
	.live-leaderboard {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.lb-row {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.3rem 0.5rem;
		border-radius: 4px;
		background: #252545;
		font-size: 0.8rem;
	}

	.lb-row.lb-mine {
		border: 1px solid #7ec8e3;
	}

	.lb-row.lb-bankrupt {
		opacity: 0.35;
	}

	.lb-rank {
		color: #888;
		min-width: 22px;
		font-size: 0.75rem;
	}

	.lb-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* ── Order history ──────────────────────────────────────────────────────── */
	.order-history {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.oh-row {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.3rem 0.5rem;
		background: #252545;
		border-radius: 4px;
		font-size: 0.78rem;
		flex-wrap: wrap;
	}

	.oh-row.oh-delivered {
		opacity: 0.6;
	}

	.oh-route {
		flex: 1;
		font-size: 0.75rem;
	}

	.oh-qty {
		color: #aaa;
		font-size: 0.75rem;
	}

	.oh-status {
		font-size: 0.68rem;
		font-weight: 700;
		text-transform: uppercase;
		border-radius: 3px;
		padding: 0.1rem 0.3rem;
	}

	.status-in_transit { background: #c8a227; color: #fff; }
	.status-delivered  { background: #27ae60; color: #fff; }
	.status-failed     { background: #c0392b; color: #fff; }

	.oh-cost {
		color: #e74c3c;
		font-size: 0.75rem;
		margin-left: auto;
	}

	/* ── Leaderboard ────────────────────────────────────────────────────────── */
	.leaderboard-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.35rem 0;
		border-bottom: 1px solid #2e2e4e;
		font-size: 0.85rem;
	}

	.rank {
		color: #888;
		min-width: 24px;
	}

	/* ── Utility ────────────────────────────────────────────────────────────── */
	.error-banner {
		background: #f8d7da;
		color: #721c24;
		border: 1px solid #f5c6cb;
		border-radius: 6px;
		padding: 0.75rem 1rem;
		margin: 1rem;
		font-family: system-ui, sans-serif;
	}

	.loading {
		color: #555;
		padding: 2rem;
		text-align: center;
		font-family: system-ui, sans-serif;
	}

	.error {
		color: #e74c3c;
		font-size: 0.82rem;
		margin: 0;
	}

	.success {
		color: #2ecc71;
		font-size: 0.82rem;
		margin: 0;
	}

	.btn-primary {
		background: #c8a227;
		color: #fff;
		border: none;
		border-radius: 6px;
		padding: 0.55rem 1.2rem;
		font-size: 0.9rem;
		cursor: pointer;
		transition: background 0.15s;
	}

	.btn-primary:hover {
		background: #a8841f;
	}

	.btn-secondary {
		display: inline-block;
		background: #6c757d;
		color: #fff;
		border: none;
		border-radius: 6px;
		padding: 0.55rem 1.2rem;
		font-size: 0.9rem;
		text-decoration: none;
		cursor: pointer;
		transition: background 0.15s;
		text-align: center;
		margin-top: 0.5rem;
	}

	.btn-secondary:hover {
		background: #545b62;
	}

	/* ── City marker styles (applied via DOM class in map.ts) ───────────────── */
	:global(.city-marker) {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		border: 2px solid #fff;
		cursor: pointer;
		box-shadow: 0 0 4px rgba(0,0,0,0.4);
	}

	:global(.city-marker.factory)     { background: #e74c3c; }
	:global(.city-marker.distributor) { background: #e67e22; }
	:global(.city-marker.wholesaler)  { background: #2980b9; }
	:global(.city-marker.retailer)    { background: #27ae60; }

	:global(.city-marker.player-city) {
		width: 18px;
		height: 18px;
		box-shadow: 0 0 0 4px rgba(255,255,255,0.5), 0 0 8px rgba(200,162,39,0.8);
		animation: city-pulse 2s infinite;
	}

	@keyframes city-pulse {
		0%, 100% { box-shadow: 0 0 0 4px rgba(255,255,255,0.5), 0 0 8px rgba(200,162,39,0.8); }
		50%       { box-shadow: 0 0 0 8px rgba(255,255,255,0.2), 0 0 16px rgba(200,162,39,0.6); }
	}
</style>
