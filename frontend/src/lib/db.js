import { openDB } from 'idb';

const DB_NAME = 'MathStudioDB';
const STORE_NAME = 'computations';

export const initDB = async () => {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        store.createIndex('timestamp', 'timestamp');
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
