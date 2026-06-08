<script lang="ts">
	import { goto } from '$app/navigation';
	import { createGame } from '$lib/api';
	import { createSession, joinSession, getMapData } from '$lib/api';
	import type { Role, City, GameSession } from '$lib/types';

	// ── Classic Beer Game ──────────────────────────────────────────────────────
	const ALL_ROLES: Role[] = ['retailer', 'wholesaler', 'distributor', 'factory'];

	let selectedRoles: Set<Role> = new Set(['retailer']);
	let classicLoading = false;
	let classicError = '';

	function toggleRole(role: Role): void {
		if (selectedRoles.has(role)) {
			selectedRoles.delete(role);
		} else {
			selectedRoles.add(role);
		}
		selectedRoles = new Set(selectedRoles);
	}

	async function handleClassicStart(): Promise<void> {
		if (selectedRoles.size === 0) {
			classicError = 'Select at least one role to play as a human.';
			return;
		}
		classicLoading = true;
		classicError = '';
		try {
			const game = await createGame([...selectedRoles]);
			await goto(`/game/classic/${game.game_id}`);
		} catch (e) {
			classicError = e instanceof Error ? e.message : 'Failed to create game.';
		} finally {
			classicLoading = false;
		}
	}

	// ── Logistics Wars ─────────────────────────────────────────────────────────

	// View state: 'home' | 'create' | 'join' | 'lobby'
	let lwView: 'home' | 'create' | 'join' | 'lobby' = 'home';
	let createdSessionId = '';

	// Create session
	let createPlayerName = '';
	let createRole = '';
	let createCityId = '';
	let createLoading = false;
	let createError = '';
	let createdRoomCode = '';

	// Join session
	let joinRoomCode = '';
	let joinPlayerName = '';
	let joinRole = '';
	let joinCityId = '';
	let joinLoading = false;
	let joinError = '';

	// Map data (cities for role/city selectors)
	let mapData: Awaited<ReturnType<typeof getMapData>> | null = null;
	let mapDataError = '';

	async function loadMapData(): Promise<void> {
		try {
			mapData = await getMapData();
		} catch {
			mapDataError = 'Could not load city data from server.';
		}
	}

	function citiesForRole(role: string): City[] {
		if (!mapData) return [];
		return Object.values(mapData.cities).filter((c) => c.available_roles.includes(role));
	}

	const LW_ROLES = ['factory', 'distributor', 'wholesaler', 'retailer'];

	async function handleCreateSession(): Promise<void> {
		if (!createPlayerName.trim()) { createError = 'Enter your name.'; return; }
		if (!createRole) { createError = 'Choose a role.'; return; }
		if (!createCityId) { createError = 'Choose a city.'; return; }
		createLoading = true;
		createError = '';
		try {
			const session: GameSession = await createSession(30);
			const company = await joinSession(
				session.room_code,
				createPlayerName.trim(),
				createRole,
				createCityId,
			);
			// Persist company_id so the game board can identify this player's company
			sessionStorage.setItem(`lw_company_${session.session_id}`, company.company_id);
			createdRoomCode = session.room_code;
			createdSessionId = session.session_id;
			lwView = 'lobby';
		} catch (e) {
			createError = e instanceof Error ? e.message : 'Failed to create session.';
		} finally {
			createLoading = false;
		}
	}

	async function handleJoinSession(): Promise<void> {
		if (!joinRoomCode.trim()) { joinError = 'Enter the room code.'; return; }
		if (!joinPlayerName.trim()) { joinError = 'Enter your name.'; return; }
		if (!joinRole) { joinError = 'Choose a role.'; return; }
		if (!joinCityId) { joinError = 'Choose a city.'; return; }
		joinLoading = true;
		joinError = '';
		try {
			const roomCode = joinRoomCode.trim().toUpperCase();
			const company = await joinSession(roomCode, joinPlayerName.trim(), joinRole, joinCityId);
			// session_id is included in the join response; fall back to room code if absent
			const sid = company.session_id ?? roomCode;
			sessionStorage.setItem(`lw_company_${sid}`, company.company_id);
			await goto(`/game/${sid}`);
		} catch (e) {
			joinError = e instanceof Error ? e.message : 'Failed to join session.';
		} finally {
			joinLoading = false;
		}
	}

	function showLwView(view: 'create' | 'join'): void {
		lwView = view;
		loadMapData();
	}
</script>

<main>
	<h1>Beer Game: The Next Level</h1>

	<!-- ── Logistics Wars ─────────────────────────────────────────────── -->
	<section class="card lw-card">
		<h2>Logistics Wars <span class="badge-new">Real-time multiplayer</span></h2>
		<p>Manage a European supply chain company on a live map. Watch shipments move in real-time.</p>

		{#if lwView === 'home'}
			<div class="btn-row">
				<button class="btn-primary" onclick={() => showLwView('create')}>Create Session</button>
				<button class="btn-secondary" onclick={() => showLwView('join')}>Join Session</button>
			</div>

		{:else if lwView === 'create'}
			<button class="btn-back" onclick={() => (lwView = 'home')}>&larr; Back</button>
			<h3>Create a new session</h3>

			<div class="form-group">
				<label for="create-name">Your name</label>
				<input id="create-name" type="text" placeholder="e.g. Alice" bind:value={createPlayerName} />
			</div>

			<div class="form-group">
				<label for="create-role">Your role</label>
				<select id="create-role" bind:value={createRole} onchange={() => (createCityId = '')}>
					<option value="">— choose role —</option>
					{#each LW_ROLES as r}
						<option value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
					{/each}
				</select>
			</div>

			{#if createRole}
				<div class="form-group">
					<label for="create-city">Your city</label>
					{#if mapDataError}
						<p class="error">{mapDataError}</p>
					{:else if !mapData}
						<p class="muted">Loading cities...</p>
					{:else}
						<select id="create-city" bind:value={createCityId}>
							<option value="">— choose city —</option>
							{#each citiesForRole(createRole) as city}
								<option value={city.city_id}>{city.name}, {city.country}</option>
							{/each}
						</select>
					{/if}
				</div>
			{/if}

			{#if createError}<p class="error">{createError}</p>{/if}

			<button class="btn-primary" onclick={handleCreateSession} disabled={createLoading}>
				{createLoading ? 'Creating...' : 'Create Session'}
			</button>

		{:else if lwView === 'lobby'}
		<h3>Session created!</h3>
		<p>Share this code with other players so they can join:</p>
		<div class="room-code-box">{createdRoomCode}</div>
		<p class="muted">Others go to "Join Session" and enter the code above.</p>
		<button class="btn-primary" onclick={() => goto(`/game/${createdSessionId}`)}>
			Enter Game Room →
		</button>

	{:else if lwView === 'join'}
			<button class="btn-back" onclick={() => (lwView = 'home')}>&larr; Back</button>
			<h3>Join an existing session</h3>

			<div class="form-group">
				<label for="join-code">Room code</label>
				<input id="join-code" type="text" placeholder="e.g. ABCD12" bind:value={joinRoomCode} />
			</div>

			<div class="form-group">
				<label for="join-name">Your name</label>
				<input id="join-name" type="text" placeholder="e.g. Bob" bind:value={joinPlayerName} />
			</div>

			<div class="form-group">
				<label for="join-role">Your role</label>
				<select id="join-role" bind:value={joinRole} onchange={() => (joinCityId = '')}>
					<option value="">— choose role —</option>
					{#each LW_ROLES as r}
						<option value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
					{/each}
				</select>
			</div>

			{#if joinRole}
				<div class="form-group">
					<label for="join-city">Your city</label>
					{#if mapDataError}
						<p class="error">{mapDataError}</p>
					{:else if !mapData}
						<p class="muted">Loading cities...</p>
					{:else}
						<select id="join-city" bind:value={joinCityId}>
							<option value="">— choose city —</option>
							{#each citiesForRole(joinRole) as city}
								<option value={city.city_id}>{city.name}, {city.country}</option>
							{/each}
						</select>
					{/if}
				</div>
			{/if}

			{#if joinError}<p class="error">{joinError}</p>{/if}

			<button class="btn-primary" onclick={handleJoinSession} disabled={joinLoading}>
				{joinLoading ? 'Joining...' : 'Join Session'}
			</button>
		{/if}
	</section>

	<!-- ── Classic Beer Game ──────────────────────────────────────────── -->
	<section class="card">
		<h2>Classic Beer Game <span class="badge-classic">Single-player / AI</span></h2>
		<p>Choose which roles you will play. AI fills the remaining positions.</p>

		<fieldset>
			<legend>Your role(s)</legend>
			<div class="role-grid">
				{#each ALL_ROLES as role}
					<label class="role-label" class:selected={selectedRoles.has(role)}>
						<input
							type="checkbox"
							checked={selectedRoles.has(role)}
							onchange={() => toggleRole(role)}
						/>
						{role.charAt(0).toUpperCase() + role.slice(1)}
					</label>
				{/each}
			</div>
		</fieldset>

		<div class="supply-chain-preview">
			<span class="node factory">Factory</span>
			<span class="arrow">&#8594;</span>
			<span class="node distributor">Distributor</span>
			<span class="arrow">&#8594;</span>
			<span class="node wholesaler">Wholesaler</span>
			<span class="arrow">&#8594;</span>
			<span class="node retailer">Retailer</span>
			<span class="arrow">&#8594;</span>
			<span class="node customer">Customer</span>
		</div>

		{#if classicError}
			<p class="error">{classicError}</p>
		{/if}

		<button class="btn-primary" onclick={handleClassicStart} disabled={classicLoading}>
			{classicLoading ? 'Starting...' : 'Start Classic Game'}
		</button>
	</section>
</main>

<style>
	main {
		max-width: 680px;
		margin: 2rem auto;
		padding: 0 1rem;
		font-family: system-ui, sans-serif;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	h1 {
		font-size: 2rem;
		margin-bottom: 0;
		color: #c8a227;
	}

	.card {
		background: #fafafa;
		border: 1px solid #ddd;
		border-radius: 8px;
		padding: 1.5rem;
	}

	.lw-card {
		border-color: #2980b9;
		background: #f0f7ff;
	}

	h2 {
		margin-top: 0;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	h3 {
		margin-top: 0.75rem;
		font-size: 1rem;
		color: #333;
	}

	.badge-new {
		font-size: 0.7rem;
		background: #2980b9;
		color: #fff;
		border-radius: 4px;
		padding: 0.15rem 0.45rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.badge-classic {
		font-size: 0.7rem;
		background: #6c757d;
		color: #fff;
		border-radius: 4px;
		padding: 0.15rem 0.45rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.btn-row {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin-top: 0.75rem;
	}

	.room-code-box {
		font-size: 2.5rem;
		font-weight: 800;
		letter-spacing: 0.3em;
		text-align: center;
		padding: 1rem;
		background: #1a1a2e;
		color: #f0c040;
		border-radius: 8px;
		margin: 0.75rem 0;
		cursor: pointer;
		user-select: all;
	}

	.btn-back {
		background: none;
		border: none;
		color: #2980b9;
		font-size: 0.9rem;
		cursor: pointer;
		padding: 0;
		margin-bottom: 0.5rem;
		text-decoration: underline;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		margin-bottom: 0.85rem;
	}

	.form-group label {
		font-size: 0.9rem;
		font-weight: 600;
		color: #444;
	}

	.form-group input,
	.form-group select {
		padding: 0.45rem 0.6rem;
		border: 1px solid #bbb;
		border-radius: 5px;
		font-size: 0.95rem;
		background: #fff;
	}

	.muted {
		color: #888;
		font-size: 0.85rem;
		margin: 0;
	}

	/* Classic role grid */
	fieldset {
		border: 1px solid #ccc;
		border-radius: 6px;
		padding: 0.75rem 1rem;
		margin-bottom: 1.25rem;
	}

	legend {
		font-weight: 600;
		padding: 0 0.25rem;
	}

	.role-grid {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin-top: 0.5rem;
	}

	.role-label {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.75rem;
		border: 2px solid #ccc;
		border-radius: 6px;
		cursor: pointer;
		user-select: none;
		font-size: 0.95rem;
		transition: border-color 0.15s, background 0.15s;
	}

	.role-label.selected {
		border-color: #c8a227;
		background: #fff8e1;
	}

	.role-label input {
		accent-color: #c8a227;
	}

	.supply-chain-preview {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin-bottom: 1.25rem;
		font-size: 0.85rem;
		color: #555;
	}

	.node {
		padding: 0.3rem 0.6rem;
		border-radius: 4px;
		background: #e8e8e8;
		font-weight: 500;
	}

	.node.customer {
		background: #d4edda;
	}

	.arrow {
		color: #999;
	}

	.error {
		color: #c0392b;
		margin-bottom: 0.75rem;
		font-size: 0.9rem;
	}

	.btn-primary {
		background: #c8a227;
		color: #fff;
		border: none;
		border-radius: 6px;
		padding: 0.65rem 1.5rem;
		font-size: 1rem;
		cursor: pointer;
		transition: background 0.15s;
	}

	.btn-primary:hover:not(:disabled) {
		background: #a8841f;
	}

	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-secondary {
		display: inline-block;
		background: #6c757d;
		color: #fff;
		border: none;
		border-radius: 6px;
		padding: 0.65rem 1.5rem;
		font-size: 1rem;
		cursor: pointer;
		transition: background 0.15s;
		text-decoration: none;
	}

	.btn-secondary:hover:not(:disabled) {
		background: #545b62;
	}
</style>
