/**
 * TypeScript types mirroring the backend Pydantic models in core/models/game.py.
 * Keep in sync with Role, PlayerState, RoundSnapshot, GameState.
 */

export type Role = 'retailer' | 'wholesaler' | 'distributor' | 'factory';

export const ROLES: Role[] = ['retailer', 'wholesaler', 'distributor', 'factory'];

/** Supply chain order: downstream (retailer) → upstream (factory) */
export const ROLE_ORDER: Role[] = ['retailer', 'wholesaler', 'distributor', 'factory'];

export interface PlayerState {
	role: Role;
	inventory: number;
	backlog: number;
	shipping_pipeline: number[];
	incoming_shipment: number;
	incoming_order: number;
	order_placed: number;
	cost_this_round: number;
	total_cost: number;
	is_human: boolean;
}

export interface RoundSnapshot {
	round_number: number;
	players: Record<string, PlayerState>;
}

export type GameStatus = 'waiting' | 'active' | 'complete';

export interface GameState {
	game_id: string;
	round: number;
	max_rounds: number;
	status: GameStatus;
	players: Record<string, PlayerState>;
	history: RoundSnapshot[];
	customer_demand: number;
	orders_this_round: Record<string, number>;
}

/** Request body for POST /api/games */
export interface CreateGameRequest {
	human_roles: Role[];
}

/** Request body for POST /api/games/{game_id}/orders */
export interface SubmitOrdersRequest {
	orders: Record<string, number>;
}

/** WebSocket message from backend */
export interface WsMessage {
	type: 'state_update' | 'error';
	state?: GameState;
	message?: string;
}

// ── Logistics Wars types ─────────────────────────────────────────────────────
// Mirror the backend Pydantic models for the real-time multiplayer variant.

export type TransportMode = 'truck' | 'train' | 'ship';

export type Company = {
	company_id: string;
	player_id: string;
	player_name: string;
	role: string;
	city_id: string;
	/** Present on join response so the client can navigate to the correct session */
	session_id?: string;
	cash: number;
	inventory: number;
	backlog: number;
	total_revenue: number;
	total_costs: number;
	is_bankrupt: boolean;
};

export type Shipment = {
	shipment_id: string;
	session_id: string;
	from_company_id: string;
	to_company_id: string;
	from_city: string;
	to_city: string;
	quantity: number;
	transport_mode: TransportMode;
	status: 'in_transit' | 'delivered' | 'failed';
	departs_at: number; // unix timestamp (seconds)
	arrives_at: number;
	shipping_cost: number;
};

export type GameSession = {
	session_id: string;
	room_code: string;
	status: 'lobby' | 'active' | 'complete';
	duration_minutes: number;
	started_at: number;
	ends_at: number;
	companies: Record<string, Company>;
	shipments: Record<string, Shipment>;
	last_demand_tick: number;
	demand_interval_seconds: number;
	customer_demand_per_tick: number;
};

export type City = {
	city_id: string;
	name: string;
	country: string;
	lat: number;
	lon: number;
	available_roles: string[];
};

export type RouteMode = {
	mode: TransportMode;
	transit_minutes: number;
	cost_per_unit: number;
	min_quantity: number;
};

export type Route = {
	from_city: string;
	to_city: string;
	modes: RouteMode[];
};

export type MapData = {
	cities: Record<string, City>;
	routes: Route[];
	upstream_role: Record<string, string | null>;
	downstream_role: Record<string, string | null>;
};

export type LeaderboardEntry = {
	company_id: string;
	player_name: string;
	role: string;
	city_id: string;
	cash: number;
	profit_loss: number;
	is_bankrupt: boolean;
	rank: number;
};
