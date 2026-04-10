import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm';

const APP_CONFIG = window.__APP_CONFIG__ || {};
const SUPABASE_URL = APP_CONFIG.supabaseUrl || window.__SUPABASE_URL__ || '';
const SUPABASE_ANON_KEY = APP_CONFIG.supabaseAnonKey || window.__SUPABASE_ANON_KEY__ || '';
const SUPABASE_SCHEMA = APP_CONFIG.supabaseSchema || 'public';
const TABLES = {
    cafes: APP_CONFIG.cafesTable || 'cafes_with_feedback', 
    likes: APP_CONFIG.likesTable || 'cafe_likes',
    comments: APP_CONFIG.commentsTable || 'cafe_comments',
    locations: 'locations'
};
const LOCAL_FEEDBACK_KEY = 'coffeeGuideLocalFeedback';
const LOCAL_LIKED_KEY = 'coffeeGuideViewerLikes';
const LOCAL_COMMENT_LOCK_KEY = 'coffeeGuideCommentLocks';
const VIEWER_ID_KEY = 'coffeeGuideViewerId';
const COMMENT_PREVIEW_LIMIT = 2;

const state = {
    cafes: [],
    feedback: {},
    currentResults: [],
    viewerId: null, // Initialized in bootstrap for robustness
    supabase: null,
    map: null,
    markersLayer: null
};

const dom = {
    countSpan: null,
    form: null,
    slider: null,
    display: null,
    resultsSection: null,
    resultsContainer: null,
    locationSelect: null,
    modal: null,
    modalTitle: null,
    iframe: null,
    closeModal: null
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
} else {
    bootstrap();
}

async function bootstrap() {
    dom.countSpan = document.getElementById('total-cafes');
    dom.form = document.getElementById('preference-form');
    dom.slider = document.getElementById('taste-slider');
    dom.display = document.getElementById('taste-display');
    dom.resultsSection = document.getElementById('results-section');
    dom.resultsContainer = document.getElementById('results-container');
    dom.locationSelect = document.getElementById('location');
    dom.modal = document.getElementById('reviews-modal');
    dom.modalTitle = document.getElementById('modal-title');
    dom.iframe = document.getElementById('reviews-iframe');
    dom.closeModal = document.querySelector('.close-modal');

    state.viewerId = getOrCreateViewerId();
    window.MCG_DEBUG = state;
    
    initSupabaseClient();
    if (state.supabase) {
        console.log('%c[Supabase] CONNECTION SUCCESS: Connected as ' + state.viewerId, 'color: #2ecc71; font-weight: bold;');
    } else {
        console.error('%c[Supabase] CONNECTION FAILED: Check your config.', 'color: #e74c3c; font-weight: bold;');
    }

    initSlider();
    bindEvents();
    updateTotalCount(0);

    try {
        const cafes = await loadCafes();
        state.cafes = cafes;
        updateTotalCount(cafes.length);
        
        // Final debug table to prove data content
        console.log('%c[DEBUG] PROOF OF DATA CONTENT:', 'color: #3498db; font-weight: bold;');
        console.table(cafes.filter(c => c.name && (c.name.includes('Patricia') || c.name.includes('Ali') || c.name.includes('Proud Mary'))).map(c => ({
            Name: c.name,
            ID: c.id,
            Likes: c.likeCount,
            Comments: c.commentCount
        })));

        state.feedback = await loadFeedback(cafes);
        
        // Load and render dynamic locations
        const locations = await loadLocations();
        renderLocationFilter(locations);
    } catch (error) {
        console.error('Failed to initialize cafe data:', error);
        state.cafes = [];
        state.feedback = {};
        updateTotalCount(0);
    }
}

function initSupabaseClient() {
    if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
        state.supabase = null;
        return;
    }

    try {
        state.supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
            db: { schema: SUPABASE_SCHEMA }
        });
        
        // Show success notification
        const statusEl = document.getElementById('connection-status');
        if (statusEl) {
            statusEl.style.opacity = '1';
            setTimeout(() => {
                statusEl.style.opacity = '0';
            }, 3000);
        }
    } catch (error) {
        console.warn('Supabase client could not be created; falling back to local data.', error);
        state.supabase = null;
    }
}

function initSlider() {
    if (!dom.slider || !dom.display) return;
    dom.slider.addEventListener('input', (event) => updateSliderLabel(event.target.value));
    updateSliderLabel(dom.slider.value);
}

function bindEvents() {
    if (dom.form) {
        dom.form.addEventListener('submit', handleRecommendationSubmit);
    }

    if (dom.closeModal) {
        dom.closeModal.addEventListener('click', closeModal);
    }

    if (dom.modal) {
        window.addEventListener('click', (event) => {
            if (event.target === dom.modal) {
                closeModal();
            }
        });
    }

    if (dom.resultsContainer) {
        dom.resultsContainer.addEventListener('click', handleResultsClick);
        dom.resultsContainer.addEventListener('submit', handleResultsSubmit);
    }
}

function updateTotalCount(count) {
    if (dom.countSpan) {
        dom.countSpan.textContent = String(count);
    }
}

function updateSliderLabel(value) {
    const labels = {
        1: '🍓 강한 산미 (High Acidity)',
        2: '🍊 은은한 산미 (Soft Acidity)',
        3: '⚖️ 밸런스 (Balanced)',
        4: '🥜 고소함 & 부드러움 (Nutty)',
        5: '🍫 묵직함 & 초콜릿 (Dark)'
    };
    dom.display.innerHTML = labels[value] || labels[3];
}

async function handleRecommendationSubmit(event) {
    event.preventDefault();
    if (!state.cafes.length) {
        dom.resultsContainer.innerHTML = renderEmptyState('아직 카페 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
        dom.resultsSection.classList.remove('hidden');
        return;
    }

    const tastePref = parseInt(dom.slider.value, 10);
    const atmosphere = document.getElementById('atmosphere').value;
    const location = document.getElementById('location').value;

    const suggestions = state.cafes
        .filter((shop) => matchesFilters(shop, atmosphere, location))
        .sort((a, b) => {
            const keyA = getCafeKey(a);
            const keyB = getCafeKey(b);
            const fbA = state.feedback[keyA] || { likeCount: 0 };
            const fbB = state.feedback[keyB] || { likeCount: 0 };

            // 1. Priority: Likes Count
            if (fbB.likeCount !== fbA.likeCount) {
                return fbB.likeCount - fbA.likeCount;
            }
            // 2. Priority: Comments Count
            if (b.commentCount !== a.commentCount) {
                return b.commentCount - a.commentCount;
            }
            // 3. Priority: Google Reviews Count
            if (b.reviews !== a.reviews) {
                return b.reviews - a.reviews;
            }
            // 4. Default: Taste Spectrum proximity
            return Math.abs(a.spectrum - tastePref) - Math.abs(b.spectrum - tastePref);
        });

    state.currentResults = suggestions;
    renderResults(suggestions);
    updateMap(suggestions);

    dom.resultsSection.classList.remove('hidden');
    dom.resultsSection.scrollIntoView({ behavior: 'smooth' });

    setTimeout(() => {
        if (state.map) {
            state.map.invalidateSize();
            if (state.markersLayer && Object.keys(state.markersLayer._layers).length > 0) {
                state.map.fitBounds(state.markersLayer.getBounds(), { padding: [30, 30] });
            }
        }
    }, 100);
}

function matchesFilters(shop, atmosphere, location) {
    if (location !== 'any') {
        // Exact match check - handles Carlton, Others, and all other regions precisely
        if (shop.location !== location) return false;
    }

    if (atmosphere !== 'any') {
        const atmospheres = Array.isArray(shop.atmosphere) ? shop.atmosphere : [];
        if (!atmospheres.includes(atmosphere)) return false;
    }

    return true;
}

function isCbdSuburb(suburb) {
    const normalized = suburb.toLowerCase();
    return normalized.includes('cbd') || (normalized.includes('melbourne') && !normalized.includes('south') && !normalized.includes('north'));
}

async function loadCafes() {
    if (state.supabase) {
        try {
            const { data, error } = await state.supabase
                .from(TABLES.cafes)
                .select('*')
                .eq('active', true)
                .order('rating', { ascending: false });

            if (error) throw error;
            if (Array.isArray(data) && data.length) {
                return data.map(normalizeCafe);
            }
        } catch (error) {
            console.warn('Supabase cafe load failed, falling back to local data.json.', error);
        }
    }

    return loadLocalCafes();
}

async function loadLocations() {
    console.log('%c[Supabase] FETCHING LOCATIONS...', 'color: #3498db;');
    const { data, error } = await state.supabase
        .from(TABLES.locations)
        .select('*')
        .order('name', { ascending: true });

    if (error) {
        console.error('Error loading locations:', error);
        return [];
    }
    return data || [];
}

function renderLocationFilter(locations) {
    if (!dom.locationSelect) return;
    
    // Keep the first "All Locations" option
    const firstOption = dom.locationSelect.options[0];
    dom.locationSelect.innerHTML = '';
    dom.locationSelect.appendChild(firstOption);

    locations.forEach(loc => {
        const option = document.createElement('option');
        option.value = loc.name;
        option.textContent = loc.name;
        dom.locationSelect.appendChild(option);
    });
}


async function loadLocalCafes() {
    const response = await fetch('data.json', { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`Failed to load local cafe data: ${response.status}`);
    }

    const data = await response.json();
    return Array.isArray(data) ? data.map(normalizeCafe).filter((cafe) => cafe.active !== false) : [];
}

function normalizeCafe(row) {
    const cafe = { ...row };
    cafe.id = row.id ?? row.cafe_id ?? slugify(row.name || 'cafe');
    cafe.name = row.name || 'Unnamed Cafe';
    cafe.location = row.location || row.suburb || 'Others';
    cafe.suburb = row.suburb || row.location || '';
    cafe.spectrum = toNumber(row.spectrum ?? row.taste ?? 3, 3);
    cafe.price = toNumber(row.price ?? 3, 3);
    cafe.atmosphere = normalizeList(row.atmosphere);
    cafe.tags = normalizeList(row.tags);
    cafe.desc = row.desc || row.description || '';
    cafe.oneLiner = row.oneLiner || row.one_liner || '';
    cafe.image = row.image || '';
    cafe.rating = toNumber(row.rating ?? 0, 0);
    cafe.reviews = toNumber(row.reviews ?? 0, 0);
    cafe.lat = row.lat === '' || row.lat == null ? null : toNumber(row.lat, null);
    cafe.lng = row.lng === '' || row.lng == null ? null : toNumber(row.lng, null);
    cafe.signature = row.signature || '';
    cafe.active = row.active === undefined ? true : Boolean(row.active);
    cafe.image_url = row.image_url || row.image || '';
    cafe.image_path = row.image_path || '';
    cafe.last_scraped_at = row.last_scraped_at || null;
    
    // Aggregate feedback from view or local fallback
    cafe.likeCount = toNumber(row.like_count ?? 0, 0);
    cafe.commentCount = toNumber(row.approved_comment_count ?? 0, 0);
    
    return cafe;
}

function normalizeList(value) {
    if (Array.isArray(value)) {
        return value.map((item) => String(item).trim()).filter(Boolean);
    }

    if (typeof value === 'string') {
        return value
            .split('|')
            .map((item) => item.trim())
            .filter(Boolean);
    }

    if (value == null) return [];
    return [String(value).trim()].filter(Boolean);
}

function toNumber(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

async function loadFeedback(cafes) {
    const feedback = buildEmptyFeedbackMap(cafes);

    if (state.supabase && cafes.every((cafe) => cafe.id !== undefined && cafe.id !== null && cafe.id !== '')) {
        try {
            const cafeIds = cafes.map((cafe) => cafe.id);
            const [likesResult, commentsResult] = await Promise.all([
                state.supabase
                    .from(TABLES.likes)
                    .select('cafe_id, viewer_id')
                    .in('cafe_id', cafeIds),
                state.supabase
                    .from(TABLES.comments)
                    .select('cafe_id, display_name, comment_text, created_at, status')
                    .in('cafe_id', cafeIds)
                    .in('status', ['approved', 'pending'])
                    .order('created_at', { ascending: false })
            ]);

            if (likesResult.error) throw likesResult.error;
            if (commentsResult.error) throw commentsResult.error;

            (likesResult.data || []).forEach((row) => {
                const key = String(row.cafe_id);
                if (!feedback[key]) return;
                feedback[key].likeCount += 1;
                if (String(row.viewer_id) === state.viewerId) {
                    feedback[key].viewerLiked = true;
                }
            });

            (commentsResult.data || []).forEach((row) => {
                const key = String(row.cafe_id);
                if (!feedback[key]) return;
                feedback[key].comments.push({
                    displayName: row.display_name || '익명',
                    commentText: row.comment_text || '',
                    createdAt: row.created_at || new Date().toISOString(),
                    status: row.status || 'approved'
                });
            });

            Object.values(feedback).forEach((entry) => {
                entry.comments = entry.comments
                    .filter((comment) => comment.status !== 'pending' || String(comment.displayName || '') === '익명')
                    .slice(0, COMMENT_PREVIEW_LIMIT);
            });

            return feedback;
        } catch (error) {
            console.warn('Supabase feedback load failed, falling back to localStorage state.', error);
        }
    }

    return loadLocalFeedback(cafes, feedback);
}

function buildEmptyFeedbackMap(cafes) {
    return cafes.reduce((acc, cafe) => {
        const key = getCafeKey(cafe);
        acc[key] = {
            likeCount: 0,
            viewerLiked: false,
            comments: []
        };
        return acc;
    }, {});
}

function loadLocalFeedback(cafes, feedbackSeed = null) {
    const localData = readJsonStorage(LOCAL_FEEDBACK_KEY, {});
    const likedSet = new Set(readJsonStorage(LOCAL_LIKED_KEY, []));
    const feedback = feedbackSeed || buildEmptyFeedbackMap(cafes);

    cafes.forEach((cafe) => {
        const key = getCafeKey(cafe);
        const entry = localData[key] || {};
        feedback[key] = {
            likeCount: toNumber(entry.likeCount, 0),
            viewerLiked: likedSet.has(key),
            comments: Array.isArray(entry.comments)
                ? entry.comments.slice(0, COMMENT_PREVIEW_LIMIT).map((comment) => ({
                    displayName: comment.displayName || '익명',
                    commentText: comment.commentText || '',
                    createdAt: comment.createdAt || new Date().toISOString()
                }))
                : []
        };
    });

    return feedback;
}

function readJsonStorage(key, fallback) {
    try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
    } catch {
        return fallback;
    }
}

function writeJsonStorage(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
}

function getOrCreateViewerId() {
    try {
        let viewerId = localStorage.getItem(VIEWER_ID_KEY);
        // Ensure it's a valid non-null string
        if (!viewerId || viewerId === 'undefined' || viewerId === 'null') {
            viewerId = (window.crypto && window.crypto.randomUUID) 
                ? crypto.randomUUID() 
                : 'v_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
            localStorage.setItem(VIEWER_ID_KEY, viewerId);
        }
        return viewerId;
    } catch (err) {
        console.warn('LocalStorage access failed, using session-only viewerId');
        return 'temp_' + Math.random().toString(36).slice(2);
    }
}

function cryptoRandomString() {
    if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
        const buffer = new Uint32Array(4);
        window.crypto.getRandomValues(buffer);
        return Array.from(buffer, (item) => item.toString(16)).join('');
    }
    return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

function getCafeKey(cafe) {
    return String(cafe.id ?? cafe.cafe_id ?? slugify(cafe.name || 'cafe'));
}

function slugify(value) {
    return String(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'cafe';
}

function renderResults(shops) {
    if (!dom.resultsContainer) return;
    dom.resultsContainer.innerHTML = '';

    if (!shops.length) {
        dom.resultsContainer.innerHTML = renderEmptyState('😢 조건에 맞는 카페가 없습니다. 가격대나 위치 조건을 조금 변경해보세요!');
        return;
    }

    const fragment = document.createDocumentFragment();

    shops.forEach((shop) => {
        const overrides = getCafeOverrides(shop.name);
        const displayImage = overrides.image || shop.image_url || shop.image;
        const displayOneLiner = overrides.oneLiner || shop.oneLiner;
        const feedback = state.feedback[getCafeKey(shop)] || { likeCount: 0, viewerLiked: false, comments: [] };
        const card = document.createElement('div');
        card.className = 'result-card';
        card.dataset.cafeKey = getCafeKey(shop);
        card.dataset.cafeName = shop.name;

        const tagsHtml = (Array.isArray(shop.tags) ? shop.tags : []).map((tag) => {
            let cls = '';
            if (tag.includes('Acidity')) cls = 'fruity';
            else if (tag.includes('Nutty') || tag.includes('Balance')) cls = 'nutty';
            return `<span class="tag ${cls}">${escapeHTML(tag)}</span>`;
        }).join('');

        const commentsHtml = feedback.comments.length
            ? feedback.comments.map((comment) => `
                <div class="comment-preview-item">
                    <span class="comment-author">${escapeHTML(comment.displayName || '익명')}</span>
                    <span class="comment-text">${escapeHTML(comment.commentText)}</span>
                </div>
            `).join('')
            : '<div class="comment-empty">아직 댓글이 없어요. 첫 한 줄을 남겨보세요.</div>';

        const imageCandidates = buildCafeImageCandidates(shop, displayImage, overrides);
        const initialImage = imageCandidates.shift() || '';
        const fallbackData = encodeURIComponent(JSON.stringify(imageCandidates));

        card.innerHTML = `
            <div class="shop-image">
                <img src="${escapeHTML(initialImage)}" alt="${escapeHTML(shop.name)}" data-fallbacks="${escapeHTML(fallbackData)}" onerror="handleCafeImageFallback(this)">
            </div>
            <div class="card-header">
                <div class="header-main">
                    <h3>${escapeHTML(shop.name)}</h3>
                    <div class="google-rating">
                        <span class="star">⭐</span> <span class="rating-value">${escapeHTML(shop.rating)}</span> <span class="review-count">(${Number(shop.reviews || 0).toLocaleString()})</span>
                    </div>
                </div>
                <div class="price-badge">${'💰'.repeat(Math.max(1, Math.min(5, Number(shop.price || 1))))}</div>
            </div>
            <div class="card-body">
                <div class="shop-location">📍 ${escapeHTML(shop.suburb)}</div>
                <div class="shop-tags">${tagsHtml}</div>
                ${shop.signature ? `<div class="shop-signature">👑 <span>시그니쳐 메뉴:</span> ${escapeHTML(shop.signature)}</div>` : ''}
                <p class="shop-desc">${escapeHTML(shop.desc)}</p>
                <div class="one-liner">"${escapeHTML(displayOneLiner)}"</div>

                <section class="feedback-panel" aria-label="${escapeHTML(shop.name)} viewer feedback">
                    <div class="feedback-actions">
                        <button type="button" class="like-button ${feedback.viewerLiked ? 'liked' : ''}" data-action="toggle-like" data-cafe-key="${escapeHTML(getCafeKey(shop))}">
                            <span class="like-icon">${feedback.viewerLiked ? '♥' : '♡'}</span>
                            <span>좋아요</span>
                            <span class="like-count">${feedback.likeCount}</span>
                        </button>
                    </div>

                    <div class="comment-preview">
                        <div class="comment-preview-header">
                            <span class="comment-preview-title">최근 댓글</span>
                            <span class="comment-total-badge">💬 ${shop.commentCount}</span>
                        </div>
                        <div class="comment-preview-list">
                            ${commentsHtml}
                        </div>
                    </div>

                    <form class="comment-form" data-action="submit-comment" data-cafe-key="${escapeHTML(getCafeKey(shop))}">
                        <input type="text" class="comment-input" maxlength="120" placeholder="한 줄 댓글을 남겨보세요" aria-label="${escapeHTML(shop.name)} 댓글 입력">
                        <button type="submit" class="comment-submit">등록</button>
                    </form>
                    <div class="comment-hint">댓글은 한 줄로만 작성해 주세요.</div>
                </section>
            </div>
        `;

        fragment.appendChild(card);
    });

    dom.resultsContainer.appendChild(fragment);
}

function renderEmptyState(message) {
    return `
        <div class="card empty-state" style="grid-column: 1/-1; text-align: center; color: #666; padding: 40px;">
            <h3>${escapeHTML(message)}</h3>
        </div>
    `;
}

function getCafeOverrides(name) {
    try {
        const data = JSON.parse(localStorage.getItem('coffeeGuideOverrides')) || {};
        return data[name] || {};
    } catch {
        return {};
    }
}

function handleResultsClick(event) {
    const likeButton = event.target.closest('.like-button');
    if (likeButton) {
        event.preventDefault();
        event.stopPropagation();
        const card = likeButton.closest('.result-card');
        if (!card) return;
        const cafe = findCafeByCard(card);
        if (cafe) {
            toggleLike(cafe);
        }
        return;
    }

    if (event.target.closest('.comment-form') || event.target.closest('.comment-input') || event.target.closest('.comment-submit')) {
        return;
    }

    const card = event.target.closest('.result-card');
    if (card) {
        const cafeName = card.dataset.cafeName || card.querySelector('h3')?.textContent || '';
        openModal(cafeName);
    }
}

function handleResultsSubmit(event) {
    const form = event.target.closest('.comment-form');
    if (!form) return;
    event.preventDefault();
    event.stopPropagation();

    const card = form.closest('.result-card');
    const cafe = findCafeByCard(card);
    const input = form.querySelector('.comment-input');
    if (!cafe || !input) return;

    const text = normalizeCommentText(input.value);
    if (!text) return;

    submitComment(cafe, text)
        .then(() => {
            input.value = '';
        })
        .catch((error) => {
            console.warn('Comment submission failed:', error);
        });
}

function findCafeByCard(card) {
    const cafeKey = card?.dataset?.cafeKey;
    if (!cafeKey) return null;
    return state.cafes.find((cafe) => String(getCafeKey(cafe)) === String(cafeKey)) || null;
}

function normalizeCommentText(value) {
    return String(value || '')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120);
}

async function toggleLike(cafe) {
    if (!state.supabase) {
        const msg = '서버에 연결되지 않았습니다. 인터넷 연결을 확인해주세요.';
        console.error(msg);
        alert(msg);
        return;
    }

    if (!state.viewerId) {
        alert('사용자 식별자가 생성되지 않았습니다. 새로고침 후 다시 시도해주세요.');
        return;
    }

    const cafeKey = getCafeKey(cafe);
    const feedback = state.feedback[cafeKey] || { likeCount: 0, viewerLiked: false, comments: [] };
    const nextLiked = !feedback.viewerLiked;

    try {
        if (nextLiked) {
            // Target the viewer_key mapping in DB
            const { error } = await state.supabase
                .from(TABLES.likes)
                .upsert({
                    cafe_id: cafe.id,
                    viewer_id: state.viewerId,
                    source: 'web'
                }, { 
                    onConflict: 'cafe_id,viewer_key',
                    ignoreDuplicates: false 
                });
            if (error) throw error;
        } else {
            const { error } = await state.supabase
                .from(TABLES.likes)
                .delete()
                .eq('cafe_id', cafe.id)
                .eq('viewer_id', state.viewerId);
            if (error) throw error;
        }

        applyLocalLikeChange(cafeKey, nextLiked);
    } catch (error) {
        console.error('CRITICAL ERROR: Supabase like update failed!', error);
        alert('저장 실패 에러: ' + (error.message || JSON.stringify(error)));
        applyLocalLikeChange(cafeKey, nextLiked, true);
    }
}

function applyLocalLikeChange(cafeKey, liked, forceLocalPersistence = false) {
    const feedback = state.feedback[cafeKey] || { likeCount: 0, viewerLiked: false, comments: [] };
    const likedSet = new Set(readJsonStorage(LOCAL_LIKED_KEY, []));

    if (liked && !feedback.viewerLiked) {
        feedback.likeCount += 1;
        feedback.viewerLiked = true;
        likedSet.add(cafeKey);
    } else if (!liked && feedback.viewerLiked) {
        feedback.likeCount = Math.max(0, feedback.likeCount - 1);
        feedback.viewerLiked = false;
        likedSet.delete(cafeKey);
    }

    state.feedback = {
        ...state.feedback,
        [cafeKey]: { ...feedback, comments: [...feedback.comments] }
    };

    if (forceLocalPersistence || !state.supabase) {
        persistLocalFeedback(cafeKey, state.feedback[cafeKey], likedSet);
    } else {
        // Keep local viewer state in sync so cards stay consistent across reloads in dev.
        writeJsonStorage(LOCAL_LIKED_KEY, Array.from(likedSet));
    }

    rerenderCurrentResults();
}

async function submitComment(cafe, commentText) {
    if (!state.supabase) {
        alert('서버에 연결되지 않아 댓글을 저장할 수 없습니다.');
        return;
    }
    if (!state.viewerId) {
        console.error('Missing viewerId for comment submission');
        return;
    }
    const cafeKey = getCafeKey(cafe);
    const newComment = {
        displayName: '익명',
        commentText,
        createdAt: new Date().toISOString()
    };

    try {
        if (state.supabase) {
            const { error } = await state.supabase
                .from(TABLES.comments)
                .insert({
                    cafe_id: cafe.id,
                    viewer_id: state.viewerId,
                    display_name: null,
                    comment_text: commentText,
                    status: 'pending'
                });
            if (error) throw error;
        }

        applyLocalCommentChange(cafeKey, newComment);
    } catch (error) {
        console.warn('Supabase comment update failed; saving locally instead.', error);
        applyLocalCommentChange(cafeKey, newComment, true);
    }
}

function applyLocalCommentChange(cafeKey, comment, forceLocalPersistence = false) {
    const feedback = state.feedback[cafeKey] || { likeCount: 0, viewerLiked: false, comments: [] };
    const updatedComments = [comment, ...feedback.comments].slice(0, COMMENT_PREVIEW_LIMIT);

    state.feedback = {
        ...state.feedback,
        [cafeKey]: {
            ...feedback,
            comments: updatedComments
        }
    };

    if (forceLocalPersistence || !state.supabase) {
        persistLocalFeedback(cafeKey, state.feedback[cafeKey]);
    }

    rerenderCurrentResults();
}

function persistLocalFeedback(cafeKey, feedback, likedSet = null) {
    const localStore = readJsonStorage(LOCAL_FEEDBACK_KEY, {});
    localStore[cafeKey] = {
        likeCount: feedback.likeCount,
        comments: feedback.comments
    };
    writeJsonStorage(LOCAL_FEEDBACK_KEY, localStore);

    if (likedSet) {
        writeJsonStorage(LOCAL_LIKED_KEY, Array.from(likedSet));
    }
}

function rerenderCurrentResults() {
    if (state.currentResults.length) {
        renderResults(state.currentResults);
    }
}

function updateMap(shops) {
    initMap();
    if (!state.markersLayer) return;
    state.markersLayer.clearLayers();

    let hasValidCoords = false;

    shops.forEach((shop) => {
        if (shop.lat && shop.lng) {
            hasValidCoords = true;
            const overrides = getCafeOverrides(shop.name);
            const displayImage = overrides.image || shop.image;

            const popupContent = `
                <div class="popup-cafe-name">${escapeHTML(shop.name)}</div>
                <div class="popup-suburb">📍 ${escapeHTML(shop.suburb)}</div>
                ${shop.signature ? `<div class="popup-signature">👑 시그니쳐 메뉴: ${escapeHTML(shop.signature)}</div>` : ''}
                <img class="popup-cafe-image" src="${escapeHTML(displayImage)}" alt="${escapeHTML(shop.name)}" onerror="this.style.display='none'">
            `;

            L.marker([shop.lat, shop.lng])
                .bindPopup(popupContent)
                .addTo(state.markersLayer);
        }
    });

    if (hasValidCoords) {
        state.map.fitBounds(state.markersLayer.getBounds(), { padding: [30, 30] });
    }
}

function initMap() {
    if (!state.map) {
        state.map = L.map('cafe-map').setView([-37.8136, 144.9631], 13);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(state.map);
        state.markersLayer = L.featureGroup().addTo(state.map);
    }
}

function openModal(cafeName) {
    if (!dom.modal || !dom.modalTitle || !dom.iframe) return;
    dom.modalTitle.textContent = cafeName;
    const query = encodeURIComponent(`${cafeName} Melbourne`);
    dom.iframe.src = `https://maps.google.com/maps?q=${query}&t=&z=13&ie=UTF8&iwloc=&output=embed`;
    dom.modal.classList.add('show');
}

function closeModal() {
    if (!dom.modal || !dom.iframe) return;
    dom.modal.classList.remove('show');
    setTimeout(() => {
        dom.iframe.src = '';
    }, 300);
}

function escapeHTML(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function buildCafeImageCandidates(shop, displayImage, overrides = {}) {
    const candidates = [];
    const push = (value) => {
        if (typeof value === 'string' && value.trim() && !candidates.includes(value.trim())) {
            candidates.push(value.trim());
        }
    };

    push(displayImage);
    push(shop.image_url);
    push(shop.image);
    push(overrides.image);

    const slug = String(getCafeKey(shop));
    const safeSlug = slugify(shop.name || slug);
    [
        `images/${slug}.jpg`,
        `images/${slug}.jpeg`,
        `images/${slug}.png`,
        `images/${slug}.webp`,
        `images/${safeSlug}.jpg`,
        `images/${safeSlug}.jpeg`,
        `images/${safeSlug}.png`,
        `images/${safeSlug}.webp`
    ].forEach(push);

    return candidates;
}

function handleCafeImageFallback(img) {
    try {
        const raw = img.getAttribute('data-fallbacks');
        const candidates = raw ? JSON.parse(decodeURIComponent(raw)) : [];
        const next = Array.isArray(candidates) ? candidates.shift() : null;
        if (Array.isArray(candidates)) {
            img.setAttribute('data-fallbacks', encodeURIComponent(JSON.stringify(candidates)));
        }
        if (next) {
            img.src = next;
            return;
        }
    } catch (error) {
        console.warn('Image fallback failed:', error);
    }
    img.parentElement.style.background = '#e8d5c4';
    img.style.display = 'none';
}

window.handleCafeImageFallback = handleCafeImageFallback;
window.buildCafeImageCandidates = buildCafeImageCandidates;
