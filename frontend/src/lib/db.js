import { openDB } from 'idb';

const DB_NAME = 'MathStudioDB';
const STORE_NAME = 'computations';
const SESSION_STORE = 'current_session';

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
  return db.add(STORE_NAME, {
    ...data,
    timestamp: Date.now()
  });
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
  return db.put(SESSION_STORE, messages, 'messages');
};

export const loadCurrentSession = async () => {
  const db = await initDB();
  return db.get(SESSION_STORE, 'messages');
};

export const clearCurrentSession = async () => {
  const db = await initDB();
  return db.delete(SESSION_STORE, 'messages');
};
