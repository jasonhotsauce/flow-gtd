import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { bootstrapSchema } from "./migrations.js";
import { defaultFlowDatabasePath } from "./schema.js";

export class FlowDatabaseOwner {
  readonly path: string;
  private readonly db: DatabaseSync;

  constructor(path: string = defaultFlowDatabasePath()) {
    this.path = path;
    mkdirSync(dirname(path), { recursive: true });
    this.db = new DatabaseSync(path);
  }

  bootstrap(): void {
    bootstrapSchema(this.db);
  }

  connection(): DatabaseSync {
    return this.db;
  }

  close(): void {
    this.db.close();
  }
}

export function bootstrapFlowDatabase(path?: string): FlowDatabaseOwner {
  const owner = new FlowDatabaseOwner(path);
  owner.bootstrap();
  return owner;
}
