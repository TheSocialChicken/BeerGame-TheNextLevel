import { WS_BASE } from "./api";

export class GameSocket {
  private ws: WebSocket | null = null;

  constructor(
    private gameId: string,
    private role: string,
    private onMessage: (data: unknown) => void,
  ) {}

  connect(): void {
    this.ws = new WebSocket(`${WS_BASE}/ws/${this.gameId}/${this.role}`);
    this.ws.onmessage = (event) => {
      try {
        this.onMessage(JSON.parse(event.data as string));
      } catch {
        console.error("Bad WS message:", event.data);
      }
    };
    this.ws.onerror = (e) => console.error("WS error:", e);
    this.ws.onclose = () => {
      this.ws = null;
    };
  }

  sendOrder(quantity: number): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "order", quantity }));
    }
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }
}
