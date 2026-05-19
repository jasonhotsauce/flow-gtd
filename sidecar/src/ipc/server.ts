export type SidecarTransport = "stdio";

export interface SidecarReadyEvent {
  event: "sidecar.ready";
  mode: "default" | "once";
  transport: SidecarTransport;
  version: string;
}

export interface SidecarServer {
  start(): Promise<SidecarReadyEvent>;
  stop(): Promise<void>;
}

export interface CreateSidecarServerOptions {
  once: boolean;
  version: string;
}

export function createSidecarServer(
  options: CreateSidecarServerOptions
): SidecarServer {
  let started = false;

  return {
    async start(): Promise<SidecarReadyEvent> {
      started = true;

      return {
        event: "sidecar.ready",
        mode: options.once ? "once" : "default",
        transport: "stdio",
        version: options.version
      };
    },

    async stop(): Promise<void> {
      started = false;
    }
  };
}
