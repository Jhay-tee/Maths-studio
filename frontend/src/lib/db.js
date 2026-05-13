import { openDB } from 'idb';

const DB_NAME = 'MathStudioDB';
const STORE_NAME = 'computations';
const SESSION_STORE = 'current_session';

const isPlainObject = (value) => {
  if (!value || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};

// Drops anything that can't be structured-cloned / JSON-stringified safely.
// In particular: DOM nodes like SVGSVGElement can appear inside "diagrams".
const sanitizeForStorage = (value) => {
  const seen = new WeakSet();

  const visit = (v) => {
    if (v === null || v === undefined) return v;

    const t = typeof v;
    if (t === 'string' || t === 'number' || t === 'boolean') return v;

    if (t === 'bigint') return String(v);
    if (t === 'function' || t === 'symbol') return undefined;

    if (v instanceof Date) return v.toISOString();

    // DOM / React / browser objects: drop
    if (typeof Element !== 'undefined' && v instanceof Element) return undefined;
    if (typeof HTMLElement !== 'undefined' && v instanceof HTMLElement) return undefined;
    if (typeof SVGElement !== 'undefined' && v instanceof SVGElement) return undefined;

    // React elements / internal fibers often include circular references.
    if (v && typeof v === 'object') {
      const maybeType = v.$$typeof;
      if (maybeType && typeof maybeType === 'string') return undefined;
    }

    if (Array.isArray(v)) {
      const out = [];
      for (const item of v) {
        const cleaned = visit(item);
        if (cleaned !== undefined) out.push(cleaned);
      }
      return out;
    }

    if (isPlainObject(v)) {
      if (seen.has(v)) return undefined;
      seen.add(v);
      const out = {};
      for (const [k, val] of Object.entries(v)) {
        const cleaned = visit(val);
        if (cleaned !== undefined) out[k] = cleaned;
      }
      return out;
    }

    // Other objects (e.g., instances) -> try to reduce to plain data if possible, else drop.
    // This avoids circular structures leaking into IDB.
    return undefined;
  };

  return visit(value);
};

export const initDB = async () => {
  return openDB(DB_NAME, 2, {
    upgrade(db, oldVersion) {
      if (oldVersion < 1) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        store.createIndex('timestamp', 'timestamp');
      }
      if (oldVersion < 2) {
        if (!db.objectStoreNames.contains(SESSION_STORE)) {
          db.createObjectStore(SESSION_STORE);
        }
      }
    },
  });
};

export const saveComputation = async (data) => {
  const db = await initDB();
  const safe = sanitizeForStorage({
    ...data,
    steps: data?.steps || [],
    diagrams: data?.diagrams || [],
    units: data?.units || [],
    timestamp: Date.now(),
  });
  return db.add(STORE_NAME, safe);
};

export const getHistory = async () => {
  const db = await initDB();
  return db.getAllFromIndex(STORE_NAME, 'timestamp');
};

export const deleteHistoryItem = async (id) => {
  const db = await initDB();
  return db.delete(STORE_NAME, id);
};

export const saveCurrentSession = async (messages) => {
  const db = await initDB();
  const safeMessages = sanitizeForStorage(messages) || [];
  return db.put(SESSION_STORE, safeMessages, 'messages');
};

export const loadCurrentSession = async () => {
  const db = await initDB();
  return db.get(SESSION_STORE, 'messages');
};

export const clearCurrentSession = async () => {
  const db = await initDB();
  return db.delete(SESSION_STORE, 'messages');
};
