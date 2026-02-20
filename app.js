// Google Sheets Published CSV URL
const SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSlUl1XYJfif1gd8_KSnfVuuQmKzieiaqRqhHbbaWm9IRSTGV_5nqtTrkuHXJMp8vCQtFhlg5hin6un/pub?gid=0&single=true&output=csv";

let coffeeShops = [];

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch(SHEET_CSV_URL);
        const csvText = await response.text();
        coffeeShops = parseCSV(csvText);

        // Update total cafe count on UI
        const countSpan = document.getElementById('total-cafes');
        if (countSpan) {
            countSpan.textContent = coffeeShops.length;
        }
    } catch (error) {
        console.error("Error loading coffee shop data from Google Sheets:", error);
    }

    const form = document.getElementById('preference-form');
    const slider = document.getElementById('taste-slider');
    const display = document.getElementById('taste-display');
    const resultsSection = document.getElementById('results-section');
    const resultsContainer = document.getElementById('results-container');

    slider.addEventListener('input', (e) => updateSliderLabel(e.target.value));

    function updateSliderLabel(val) {
        const labels = {
            1: "🍓 강한 산미 (High Acidity)",
            2: "🍊 은은한 산미 (Soft Acidity)",
            3: "⚖️ 밸런스 (Balanced)",
            4: "🥜 고소함 & 부드러움 (Nutty)",
            5: "🍫 묵직함 & 초콜릿 (Dark)"
        };
        display.innerHTML = labels[val] || labels[3];
    }

    // Initial call
    updateSliderLabel(slider.value);

    form.addEventListener('submit', (e) => {
        e.preventDefault();

        const tastePref = parseInt(slider.value);
        const atmosphere = document.getElementById('atmosphere').value;
        const location = document.getElementById('location').value;

        let suggestions = coffeeShops.filter(shop => {
            if (location !== 'any' && shop.location !== location) return false;
            if (atmosphere !== 'any' && !shop.atmosphere.includes(atmosphere)) return false;
            return true;
        });

        suggestions.sort((a, b) => Math.abs(a.spectrum - tastePref) - Math.abs(b.spectrum - tastePref));

        renderResults(suggestions);
        resultsSection.classList.remove('hidden');
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    });

    function renderResults(shops) {
        resultsContainer.innerHTML = '';

        if (shops.length === 0) {
            resultsContainer.innerHTML = `
                <div class="card" style="grid-column: 1/-1; text-align: center; color: #666; padding: 40px;">
                    <h3>😢 조건에 맞는 카페가 없습니다.</h3>
                    <p style="margin-top:8px;">가격대나 위치 조건을 조금 변경해보세요!</p>
                </div>`;
            return;
        }

        shops.forEach(shop => {
            // Apply admin overrides from localStorage
            const overrides = (() => {
                try {
                    const data = JSON.parse(localStorage.getItem('coffeeGuideOverrides')) || {};
                    return data[shop.name] || {};
                } catch { return {}; }
            })();
            const displayImage = overrides.image || shop.image;
            const displayOneLiner = overrides.oneLiner || shop.oneLiner;

            const el = document.createElement('div');
            el.className = 'result-card';

            const tagsHtml = shop.tags.map(tag => {
                let cls = '';
                if (tag.includes('Acidity')) cls = 'fruity';
                else if (tag.includes('Nutty') || tag.includes('Balance')) cls = 'nutty';
                return `<span class="tag ${cls}">${tag}</span>`;
            }).join('');

            el.innerHTML = `
                <div class="shop-image">
                    <img src="${displayImage}" alt="${shop.name}" onerror="this.parentElement.style.background='#e8d5c4'; this.style.display='none';">
                </div>
                <div class="card-header">
                    <div class="header-main">
                        <h3>${shop.name}</h3>
                        <div class="google-rating">
                            <span class="star">⭐</span> <span class="rating-value">${shop.rating}</span> <span class="review-count">(${shop.reviews.toLocaleString()})</span>
                        </div>
                    </div>
                    <div class="price-badge">${'💰'.repeat(shop.price)}</div>
                </div>
                <div class="card-body">
                    <div class="shop-location">📍 ${shop.suburb}</div>
                    <div class="shop-tags">${tagsHtml}</div>
                    <p class="shop-desc">${shop.desc}</p>
                    <div class="one-liner">"${displayOneLiner}"</div>
                </div>
            `;
            resultsContainer.appendChild(el);
        });
    }

    // Modal Logic
    const modal = document.getElementById('reviews-modal');
    const modalTitle = document.getElementById('modal-title');
    const iframe = document.getElementById('reviews-iframe');
    const span = document.getElementsByClassName("close-modal")[0];

    // Event Delegation for Card Clicks
    resultsContainer.addEventListener('click', (e) => {
        const card = e.target.closest('.result-card');
        if (card) {
            const cafeName = card.querySelector('h3').textContent;
            openModal(cafeName);
        }
    });

    function openModal(cafeName) {
        modalTitle.textContent = cafeName;
        // Use the legacy embed URL which works dynamically without key for simple search results
        // Note to user: This is a workaround. Official API requires key.
        const query = encodeURIComponent(cafeName + " Melbourne");
        iframe.src = `https://maps.google.com/maps?q=${query}&t=&z=13&ie=UTF8&iwloc=&output=embed`;
        modal.classList.add('show');
    }

    span.onclick = function () {
        closeModal();
    }

    window.onclick = function (event) {
        if (event.target == modal) {
            closeModal();
        }
    }


    function closeModal() {
        modal.classList.remove('show');
        setTimeout(() => {
            iframe.src = ""; // Clear src to stop playing/loading
        }, 300);
    }
});

// Helper function to parse CSV text into an array of objects
function parseCSV(csvText) {
    const lines = csvText.split('\n');
    const headers = lines[0].trim().split(',');
    const result = [];

    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        // Simple CSV parser handling quotes
        const values = [];
        let inQuotes = false;
        let currentValue = '';

        for (let j = 0; j < line.length; j++) {
            const char = line[j];
            if (char === '"') {
                if (inQuotes && line[j + 1] === '"') {
                    currentValue += '"'; // Escape quote
                    j++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                values.push(currentValue);
                currentValue = '';
            } else {
                currentValue += char;
            }
        }
        values.push(currentValue);

        const obj = {};
        headers.forEach((header, index) => {
            let val = values[index];
            if (val === undefined) return;
            // Parse specific formats based on column name
            if (header === 'spectrum' || header === 'price' || header === 'rating' || header === 'reviews') {
                obj[header] = Number(val);
            } else if (header === 'atmosphere' || header === 'tags') {
                obj[header] = val ? val.split('|') : [];
            } else {
                obj[header] = val;
            }
        });
        result.push(obj);
    }
    return result;
}
