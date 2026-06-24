'use strict';

// The active tourism app is the Flask application in app.py.
// This file stays intentionally small so JS tooling can parse it cleanly.
const TourismApp = {
    name: 'India Tourism',
    imageFallback: '/static/images/travel-fallback.svg'
};

if (typeof window !== 'undefined') {
    window.TourismApp = Object.assign(window.TourismApp || {}, TourismApp);
}

if (typeof module !== 'undefined') {
    module.exports = TourismApp;
}
