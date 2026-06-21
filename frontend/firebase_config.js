// ============================================================================
// Firebase Configuration — NutriScan
// ============================================================================
// INSTRUCTIONS:
//   1. Go to https://console.firebase.google.com/
//   2. Create a new project (or use an existing one)
//   3. Go to Project Settings > General > Your apps > Add web app
//   4. Copy your Firebase config object below
//   5. Go to Authentication > Sign-in method > Enable "Google"
//   6. Add your domain to Authorized domains (localhost is auto-added)
// ============================================================================

const firebaseConfig = {
    apiKey: "firebase_api_key",
    authDomain: "nutriscan-839dc.firebaseapp.com",
    projectId: "nutriscan-839dc",
    storageBucket: "nutriscan-839dc.firebasestorage.app",
    messagingSenderId: "844187750560",
    appId: "1:844187750560:web:a82a7a78026f6cdb87b9c5",
    measurementId: "G-17XYVGLG70"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
