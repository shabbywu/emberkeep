/** Tooling declarations for the real Python registry in game/bridge.py. */
type Direction = 'up' | 'right' | 'down' | 'left';
type Phase = 'menu' | 'playing' | 'upgrade' | 'won' | 'dead';

interface HeroProxy {
  readonly hp: number;
  readonly max_hp: number;
  readonly level: number;
  readonly attack: number;
  readonly armor: number;
  readonly potions: number;
}

// Python containers are live proxies. Copy them with Python.to_value() before rendering.
interface PythonSnapshotProxy { readonly __pythonSnapshot?: never; }
interface Snapshot {
  language: 'en' | 'zh-CN';
  catalog?: Record<string, string>;
  language_override?: boolean;
  phase: Phase;
  paused?: boolean;
  floor?: number;
  turn?: number;
  seed?: number;
  revision?: number;
  rows?: string[];
  player?: Record<string, number>;
  enemies?: Array<Record<string, unknown>>;
  events: Array<Record<string, unknown>>;
  has_save: boolean;
  saved: boolean;
  save_error: string;
}

interface Commands {
  move(direction: Direction): Promise<PythonSnapshotProxy>;
  whirl(): Promise<PythonSnapshotProxy>;
  cast_bolt(x?: number | null, y?: number | null): Promise<PythonSnapshotProxy>;
  heal(): Promise<PythonSnapshotProxy>;
  wait_turn(): Promise<PythonSnapshotProxy>;
  interact(x: number, y: number): Promise<PythonSnapshotProxy>;
}

interface LiveGameProxy extends Commands {
  readonly hero: HeroProxy;
  readonly phase: Phase;
  readonly floor: number;
  readonly turn: number;
  readonly seed: number;
}

interface HostAPI extends Commands {
  readonly game: LiveGameProxy;
  boot(): Promise<PythonSnapshotProxy>;
  new_run(seed?: number | null): Promise<PythonSnapshotProxy>;
  choose_upgrade(id: string): Promise<PythonSnapshotProxy>;
  set_language(language: 'en' | 'zh-CN'): Promise<PythonSnapshotProxy>;
  set_paused(value: boolean): Promise<PythonSnapshotProxy>;
  save_game(): Promise<PythonSnapshotProxy>;
  load_game(): Promise<PythonSnapshotProxy>;
  quit_game(): Promise<void>;
}

declare const host: HostAPI;
declare const Python: { to_value(proxy: PythonSnapshotProxy): Snapshot };
