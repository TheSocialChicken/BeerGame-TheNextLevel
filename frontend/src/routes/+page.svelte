<script lang="ts">
	import { createSession } from '$lib/api';
	import { goto } from '$app/navigation';

	let sessionId = $state('');
	let role = $state('retailer');
	const roles = ['retailer', 'wholesaler', 'distributor', 'factory'] as const;

	async function newGame() {
		try {
			const { session_id } = await createSession();
			await goto(`/game/${session_id}/retailer`);
		} catch (err) {
			alert('Failed to create game: ' + err);
		}
	}

	async function joinGame() {
		if (!sessionId.trim()) { alert('Enter a session ID'); return; }
		await goto(`/game/${sessionId.trim()}/${role}`);
	}
</script>

<div class="lobby">
	<h1>🍺 Beer Game</h1>
	<p>Supply chain simulation — 4 players, 26 rounds</p>

	<button onclick={newGame}>New Game</button>

	<hr />
	<h2>Join existing game</h2>
	<input bind:value={sessionId} placeholder="Session ID" type="text" />
	<select bind:value={role}>
		{#each roles as r}
			<option value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
		{/each}
	</select>
	<button onclick={joinGame}>Join</button>
</div>

<style>
	.lobby {
		max-width: 420px;
		margin: 4rem auto;
		padding: 2rem;
		text-align: center;
		font-family: system-ui, sans-serif;
	}
	h1 { font-size: 2rem; margin-bottom: 0.5rem; }
	p  { color: #666; margin-bottom: 2rem; }
	button {
		background: #2563eb; color: white; border: none;
		padding: 0.6rem 1.4rem; border-radius: 6px;
		font-size: 1rem; cursor: pointer; margin: 0.25rem;
	}
	button:hover { background: #1d4ed8; }
	input, select {
		padding: 0.5rem; font-size: 1rem; margin: 0.25rem;
		border: 1px solid #d1d5db; border-radius: 6px;
	}
	input { width: 100%; box-sizing: border-box; }
	hr { margin: 2rem 0; border: none; border-top: 1px solid #e5e7eb; }
</style>
