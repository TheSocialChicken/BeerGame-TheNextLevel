<svelte:options runes />
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/state';
	import { getState, submitOrder, startGame, type GameState } from '$lib/api';
	import { GameSocket } from '$lib/websocket';

	const gameId = page.params.id!;
	const role   = page.params.role!;

	let gameData: GameState | null = $state(null);
	let orderQty   = $state('');
	let statusMsg  = $state('Connecting...');
	let gameOver   = $state(false);
	let socket: GameSocket | null = null;

	async function loadState() {
		try {
			gameData = await getState(gameId, role);
		} catch (err) {
			statusMsg = 'Error loading state: ' + err;
		}
	}

	async function handleStart() {
		await startGame(gameId);
		await loadState();
		statusMsg = 'Game started!';
	}

	function handleWsMessage(data: unknown) {
		const msg = data as Record<string, unknown>;
		const event = msg.event as string;
		if (event === 'round_complete' || event === 'game_over') {
			loadState();
		}
		if (event === 'game_over') {
			gameOver = true;
			statusMsg = `Game Over! Total supply chain cost: $${msg.total_cost}`;
		}
		if (event === 'error') {
			statusMsg = 'Error: ' + msg.message;
		}
		if (event === 'order_accepted') {
			statusMsg = `Order of ${msg.quantity} accepted`;
		}
	}

	async function placeOrder() {
		const qty = parseInt(orderQty, 10);
		if (isNaN(qty) || qty < 0) { statusMsg = 'Enter valid quantity (≥ 0)'; return; }
		if (gameData?.phase !== 'active')  { statusMsg = 'Game not active'; return; }
		try {
			await submitOrder(gameId, role, qty);
			socket?.sendOrder(qty);
			orderQty  = '';
			statusMsg = `Order of ${qty} placed`;
		} catch (err) {
			statusMsg = 'Order failed: ' + err;
		}
	}

	onMount(async () => {
		await loadState();
		socket = new GameSocket(gameId, role, handleWsMessage);
		socket.connect();
		statusMsg = 'Connected';
	});

	onDestroy(() => socket?.disconnect());
</script>

<div class="board">
	<header>
		<h1>Beer Game — <span class="role">{role}</span></h1>
		<p>Round {gameData?.round ?? '–'} · Phase: <strong>{gameData?.phase ?? '–'}</strong></p>
	</header>

	{#if gameOver}
		<div class="banner">🏁 {statusMsg}</div>
	{/if}

	{#if gameData}
		<div class="stats">
			<div class="stat"><span>Inventory</span><strong>{gameData.inventory}</strong></div>
			<div class="stat"><span>Backlog</span><strong class:warn={gameData.backlog > 0}>{gameData.backlog}</strong></div>
			<div class="stat"><span>Last Order</span><strong>{gameData.last_order}</strong></div>
			<div class="stat"><span>Total Cost</span><strong>${gameData.cumulative_cost.toFixed(2)}</strong></div>
		</div>

		{#if gameData.incoming_shipments.length > 0}
			<section>
				<h3>Pipeline</h3>
				<ul>
					{#each gameData.incoming_shipments as s}
						<li>{s.quantity} units arriving in {s.arrives_in_rounds} round{s.arrives_in_rounds !== 1 ? 's' : ''}</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if gameData.phase === 'waiting'}
			<button onclick={handleStart}>Start Game</button>
		{:else if gameData.phase === 'active' && !gameOver}
			<section class="order-form">
				<h3>Place Order</h3>
				<input
					bind:value={orderQty}
					type="number" min="0" placeholder="Quantity"
					onkeydown={(e) => e.key === 'Enter' && placeOrder()}
				/>
				<button onclick={placeOrder}>Order</button>
			</section>
		{/if}
	{/if}

	<p class="status">{statusMsg}</p>
</div>

<style>
	.board {
		max-width: 600px; margin: 2rem auto;
		padding: 1.5rem; font-family: system-ui, sans-serif;
	}
	header { text-align: center; margin-bottom: 1.5rem; }
	h1 { font-size: 1.5rem; margin: 0; }
	.role { text-transform: capitalize; color: #2563eb; }
	.stats {
		display: grid; grid-template-columns: repeat(2, 1fr);
		gap: 1rem; margin-bottom: 1.5rem;
	}
	.stat {
		background: #f3f4f6; padding: 1rem; border-radius: 8px; text-align: center;
	}
	.stat span { display: block; font-size: 0.8rem; color: #6b7280; margin-bottom: 0.25rem; }
	.stat strong { font-size: 1.5rem; }
	.warn { color: #dc2626; }
	.banner {
		background: #fef3c7; border: 1px solid #f59e0b;
		padding: 1rem; border-radius: 8px; text-align: center;
		font-weight: bold; margin-bottom: 1rem;
	}
	.order-form { display: flex; gap: 0.5rem; align-items: center; }
	input[type=number] {
		padding: 0.5rem; font-size: 1rem; width: 100px;
		border: 1px solid #d1d5db; border-radius: 6px;
	}
	button {
		background: #2563eb; color: white; border: none;
		padding: 0.6rem 1.4rem; border-radius: 6px;
		font-size: 1rem; cursor: pointer;
	}
	button:hover { background: #1d4ed8; }
	ul { padding-left: 1.5rem; }
	.status { color: #6b7280; font-size: 0.9rem; margin-top: 1rem; }
</style>
