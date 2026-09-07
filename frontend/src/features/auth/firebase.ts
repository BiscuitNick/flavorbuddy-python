import { initializeApp, getApps } from "firebase/app";
import {
  initializeAuth,
  inMemoryPersistence,
  browserPopupRedirectResolver,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  connectAuthEmulator,
} from "firebase/auth";

export type FirebaseConfig = {
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId: string;
  emulatorUrl?: string;
};

export function prepareGoogle(config: FirebaseConfig) {
  const existing = getApps().find((app) => app.name === "flavorbuddy");
  const app = existing || initializeApp(config, "flavorbuddy");
  const auth = initializeAuth(app, {
    persistence: inMemoryPersistence,
    popupRedirectResolver: browserPopupRedirectResolver,
  });
  if (!existing && config.emulatorUrl)
    connectAuthEmulator(auth, config.emulatorUrl);
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  return async () => {
    try {
      const result = await signInWithPopup(auth, provider);
      return await result.user.getIdToken();
    } finally {
      // Only the HttpOnly Django session remains after the exchange.
      await signOut(auth);
    }
  };
}
