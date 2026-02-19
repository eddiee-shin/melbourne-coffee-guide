const coffeeShops = [
    // GROUP A: Fruity, Floral, Experimental (Score 1-2)
    {
        name: "Zest Specialty Coffee",
        location: "Others",
        suburb: "Richmond",
        spectrum: 1,
        price: 3,
        atmosphere: ["modern", "unique"],
        desc: "과일 주스 같은 커피. 실험적인 가공 방식으로 '호주가 가장 사랑하는 커피' 선정.",
        oneLiner: "수박, 라임 등 커피에서 상상하기 힘든 강렬한 과일 향.",
        tags: ["Acidity ⭐⭐⭐⭐⭐", "Experimental"],
        image: "images/zest_specialty.jpg"
    },
    {
        name: "ONA Coffee",
        location: "Brunswick",
        suburb: "Brunswick",
        spectrum: 1,
        price: 5,
        atmosphere: ["modern", "lively"],
        desc: "세계 바리스타 챔피언 사샤 세스틱의 카페. 라즈베리 캔디 블렌드 유명.",
        oneLiner: "커피 덕후들의 성지. 최고가의 게이샤 원두와 극한의 산미.",
        tags: ["Acidity ⭐⭐⭐⭐⭐", "Champion"],
        image: "images/ona_coffee.jpg"
    },
    {
        name: "Proud Mary",
        location: "Fitzroy/Collingwood",
        suburb: "Collingwood",
        spectrum: 1,
        price: 5,
        atmosphere: ["lively", "unique"],
        desc: "세계 100대 카페 상위권. 재즈 같은 맛, 망고 노트 등 화려한 필터 커피.",
        oneLiner: "멜번 스페셜티 커피의 자존심. 비싸지만 실패 없는 화려한 맛.",
        tags: ["Acidity ⭐⭐⭐⭐⭐", "Top 100"],
        image: "images/proud_mary.jpg"
    },
    {
        name: "ACOFFEE",
        location: "Fitzroy/Collingwood",
        suburb: "Collingwood",
        spectrum: 1,
        price: 4,
        atmosphere: ["modern", "unique"],
        desc: "로스팅을 아주 약하게 하여 원두 본연의 깨끗함을 극대화. 순백색 인테리어.",
        oneLiner: "차(Tea)처럼 맑고 깨끗한 커피를 선호한다면 최고의 선택.",
        tags: ["Acidity ⭐⭐⭐⭐⭐", "Pure"],
        image: "images/acoffee.jpg"
    },
    {
        name: "INI Studio",
        location: "Fitzroy/Collingwood",
        suburb: "Carlton/Collingwood",
        spectrum: 1,
        price: 3,
        atmosphere: ["modern", "unique"],
        desc: "시트러스 롱블랙 등 산미를 즐기는 메뉴. 미니멀리즘의 극치.",
        oneLiner: "인스타그래머블한 공간에서 즐기는 상큼하고 감각적인 커피.",
        tags: ["Acidity ⭐⭐⭐⭐⭐", "Minimal"],
        image: "images/ini_studio.jpg"
    },
    {
        name: "Market Lane Coffee",
        location: "CBD",
        suburb: "CBD / Market",
        spectrum: 2,
        price: 4,
        atmosphere: ["lively", "cozy"],
        desc: "제철 과일 같은 커피. 쓴맛 배제, 단맛과 산미의 조화.",
        oneLiner: "산미 입문자에게 가장 추천하는 곳. 부담스럽지 않고 우아한 꽃향기.",
        tags: ["Acidity ⭐⭐⭐⭐", "Elegant"],
        image: "images/market_lane.jpg"
    },
    {
        name: "Good Measure",
        location: "Others",
        suburb: "Carlton (Lygon St)",
        spectrum: 2,
        price: 3,
        atmosphere: ["cozy", "lively"],
        desc: "'몽블랑 커피'로 입소문 난 곳. 낮엔 카페, 밤엔 칵테일 바로 변신. 따뜻한 우드 인테리어.",
        oneLiner: "SNS에서 유명한 몽블랑 아이스 필터, 오렌지 제스트와 크림의 조화.",
        tags: ["Acidity ⭐⭐⭐⭐", "Cafe & Bar"],
        image: "images/good_measure.jpg"
    },
    {
        name: "Small Batch Roasting Co.",
        location: "North Melbourne",
        suburb: "North Melbourne",
        spectrum: 2,
        price: 3,
        atmosphere: ["unique", "cozy"],
        desc: "Candyman 블렌드가 유명. 달콤하면서도 잘 익은 과일의 산미.",
        oneLiner: "완벽한 페이스트리와 함께 즐기는 쥬시(Juicy)한 커피.",
        tags: ["Acidity ⭐⭐⭐⭐", "Juicy"],
        image: "images/small_batch.jpg"
    },
    {
        name: "Vacation Coffee",
        location: "CBD",
        suburb: "CBD",
        spectrum: 2,
        price: 3,
        atmosphere: ["lively", "modern"],
        desc: "휴가 같은 커피. 파스텔 톤 분위기, 밝고 경쾌한 과일 맛.",
        oneLiner: "도심 속에서 즐기는 산뜻하고 트로피컬한 커피 한 잔.",
        tags: ["Acidity ⭐⭐⭐⭐", "Tropical"],
        image: "images/vacation_coffee.jpg"
    },

    // GROUP B: Balanced & Complex (Score 3)
    {
        name: "Seven Seeds",
        location: "Others",
        suburb: "Carlton",
        spectrum: 3,
        price: 4,
        atmosphere: ["lively", "unique"],
        desc: "멜번 커피의 기준점. 산미와 단맛의 훌륭한 밸런스.",
        oneLiner: "멜번에 왔다면 무조건 가봐야 할 교과서 같은 곳.",
        tags: ["Balance ⭐⭐⭐⭐⭐", "Standard"],
        image: "images/seven_seeds.jpg"
    },
    {
        name: "Disciple Roasters",
        location: "Brunswick",
        suburb: "Brunswick",
        spectrum: 2.5,
        price: 3,
        atmosphere: ["cozy", "unique"],
        desc: "소량 생산 집중, 펀치감 있는 향미. 개성이 뚜렷함.",
        oneLiner: "숨겨진 고수. 뻔한 커피 맛에 질렸다면 추천.",
        tags: ["Acidity ⭐⭐⭐⭐", "Unique"],
        image: "images/disciple_roasters.jpg"
    },
    {
        name: "Tone Coffee",
        location: "North Melbourne",
        suburb: "North Melbourne",
        spectrum: 3,
        price: 3,
        atmosphere: ["modern", "lively"],
        desc: "2015 세계 라떼아트 챔피언 Caleb 'Tiger' Cha의 로스터리. 'Tiger Bomb' 아이스드링크로 유명.",
        oneLiner: "챔피언의 손맛. 깔끔하고 선명한 특색 있는 커피.",
        tags: ["Balance ⭐⭐⭐⭐", "Champion"],
        image: "images/tone_coffee.jpg"
    },
    {
        name: "Patricia Coffee Brewers",
        location: "CBD",
        suburb: "CBD",
        spectrum: 3,
        price: 3,
        atmosphere: ["unique", "lively"],
        desc: "스탠딩 바. 블랙, 화이트, 필터뿐. 너무 시지도 쓰지도 않은 황금비율.",
        oneLiner: "서서 마셔야 하지만 그럴 가치가 있는, 직장인들의 영혼의 안식처.",
        tags: ["Balance ⭐⭐⭐⭐⭐", "Standing Bar"],
        image: "images/patricia_coffee.jpg"
    },
    {
        name: "Bench Coffee Co.",
        location: "CBD",
        suburb: "CBD",
        spectrum: 3,
        price: 3,
        atmosphere: ["modern", "unique"],
        desc: "홍콩/일본 스타일의 미니멀리즘. 깔끔하고 군더더기 없는 맛.",
        oneLiner: "도시적인 세련됨 그 자체. 깔끔한 뒷맛을 원할 때.",
        tags: ["Balance ⭐⭐⭐⭐⭐", "Clean"],
        image: "images/bench_coffee.jpg"
    },
    {
        name: "Core Roasters",
        location: "Brunswick",
        suburb: "Brunswick East",
        spectrum: 3,
        price: 3,
        atmosphere: ["cozy"],
        desc: "지속 가능성에 진심. 'Bloody Good'을 지향하며 선명한 맛.",
        oneLiner: "착한 소비를 하면서 맛도 놓치지 않는 곳.",
        tags: ["Balance ⭐⭐⭐", "Ethical"],
        image: "images/core_roasters.jpg"
    },
    {
        name: "St Ali",
        location: "South Melbourne",
        suburb: "South Melbourne",
        spectrum: 3,
        price: 4,
        atmosphere: ["lively", "unique"],
        desc: "힙하고 거친 매력. 사과 잼 같은 산미와 퍼지 같은 단맛.",
        oneLiner: "힙스터들의 성지. 묵직하면서도 엣지 있는 커피.",
        tags: ["Balance ⭐⭐⭐", "Hipster"],
        image: "images/st_ali.jpg"
    },
    {
        name: "Axil Coffee Roasters",
        location: "CBD",
        suburb: "CBD / Multiple",
        spectrum: 3,
        price: 3,
        atmosphere: ["modern", "lively"],
        desc: "챔피언 바리스타 배출. 대중성을 고려해 산미를 튀지 않게 잡음.",
        oneLiner: "믿고 마시는 데일리 커피. 실패 확률 0%.",
        tags: ["Balance ⭐⭐⭐", "Reliable"],
        image: "images/axil_coffee.jpg"
    },
    {
        name: "Code Black Coffee",
        location: "Brunswick",
        suburb: "Brunswick",
        spectrum: 3,
        price: 3,
        atmosphere: ["modern", "unique"],
        desc: "다크 호스. 복합적인 맛. 우유와 섞였을 때 캐릭터가 강함.",
        oneLiner: "시크한 분위기에서 즐기는 진하고 깊은 풍미.",
        tags: ["Balance ⭐⭐⭐", "Dark Mode"],
        image: "images/code_black.jpg"
    },
    {
        name: "Wide Open Road",
        location: "Brunswick",
        suburb: "Brunswick",
        spectrum: 3,
        price: 3,
        atmosphere: ["cozy", "lively"],
        desc: "데일리로 마시기 좋은 부드러움과 단맛. 브런치와 곁들이기 좋음.",
        oneLiner: "편안한 분위기의 브런치 카페에서 즐기는 부담 없는 커피.",
        tags: ["Balance ⭐⭐⭐", "Brunch"],
        image: "images/wide_open_road.jpg"
    },
    {
        name: "Industry Beans",
        location: "Fitzroy/Collingwood",
        suburb: "Fitzroy",
        spectrum: 3,
        price: 4,
        atmosphere: ["modern", "lively"],
        desc: "하이테크 로스팅. 구조감이 좋고 깔끔함. 버블 커피 등 독창적 메뉴.",
        oneLiner: "세련된 공간, 과학적으로 설계된 맛.",
        tags: ["Balance ⭐⭐⭐", "High-Tech"],
        image: "images/industry_beans.jpg"
    },

    // GROUP C: Nutty, Chocolatey, Comfort (Score 4-5)
    {
        name: "Dukes Coffee Roasters",
        location: "CBD",
        suburb: "CBD",
        spectrum: 4,
        price: 3,
        atmosphere: ["cozy", "unique"],
        desc: "유기농 원두. 부드러운 목 넘김과 고소함 강조. 라떼 맛집.",
        oneLiner: "시내에서 가장 우아하고 부드러운 라떼를 파는 곳.",
        tags: ["Nutty ⭐⭐⭐⭐", "Organic"],
        image: "images/dukes_coffee.jpg"
    },
    {
        name: "Rumble Coffee",
        location: "Others",
        suburb: "Kensington",
        spectrum: 4.5,
        price: 3,
        atmosphere: ["cozy"],
        desc: "다크 초콜릿과 라즈베리 잼 풍미. 묵직한 바디감이 특징.",
        oneLiner: "강렬한 펀치 한 방. 묵직하고 진한 커피.",
        tags: ["Nutty ⭐⭐⭐⭐", "Heavy Body"],
        image: "images/rumble_coffee.jpg"
    },
    {
        name: "Padre Coffee",
        location: "Brunswick",
        suburb: "Brunswick East",
        spectrum: 5,
        price: 3,
        atmosphere: ["cozy"],
        desc: "카라멜과 밀크 초콜릿 향 지배적. 매우 부드럽고 달콤함.",
        oneLiner: "아빠 미소처럼 포근하고 달콤 고소한 커피.",
        tags: ["Nutty ⭐⭐⭐⭐⭐", "Sweet"],
        image: "images/padre_coffee.jpg"
    },
    {
        name: "Commonfolk Coffee",
        location: "Others",
        suburb: "Frankston",
        spectrum: 5,
        price: 3,
        atmosphere: ["lively", "cozy"],
        desc: "진한 흑설탕과 고소함. 대중적인 입맛을 완벽히 사로잡음.",
        oneLiner: "교외로 나간다면 필참. 마음까지 따뜻해지는 고소하고 진한 맛.",
        tags: ["Nutty ⭐⭐⭐⭐⭐", "Community"],
        image: "images/commonfolk_coffee.jpg"
    },
    {
        name: "Brother Baba Budan",
        location: "CBD",
        suburb: "CBD",
        spectrum: 5,
        price: 3,
        atmosphere: ["unique", "lively"],
        desc: "세븐 시즈 원두 사용. 우유 메뉴 위주로 빠르게 서빙. 천장의 의자.",
        oneLiner: "멜번 시내 한복판에서 즐기는 빠르고 진한 카페인 충전.",
        tags: ["Nutty ⭐⭐⭐⭐⭐", "Busy"],
        image: "images/brother_baba_budan.jpg"
    },
    {
        name: "Monk Bodhi Dharma",
        location: "Others",
        suburb: "Balaclava",
        spectrum: 5,
        price: 3,
        atmosphere: ["unique", "cozy"],
        desc: "붉은 벽돌 뒤 숨겨진 곳. 흙내음(Earthy)나고 묵직함. 비건 프렌들리.",
        oneLiner: "나만 알고 싶은 아지트에서 마시는 깊고 진한 커피.",
        tags: ["Nutty ⭐⭐⭐⭐⭐", "Vegan Friendly"],
        image: "images/monk_bodhi_dharma.jpg"
    },
    {
        name: "Higher Ground",
        location: "CBD",
        suburb: "CBD",
        spectrum: 5,
        price: 5,
        atmosphere: ["unique", "lively"],
        desc: "웅장한 공간. 대중적이고 호불호 없는 고소하고 크리미한 라떼.",
        oneLiner: "호텔 로비 같은 웅장함 속에서 즐기는 안정적인 맛.",
        tags: ["Nutty ⭐⭐⭐⭐⭐", "Grand"],
        image: "images/higher_ground.jpg"
    },
    {
        name: "Auction Rooms",
        location: "North Melbourne",
        suburb: "North Melbourne",
        spectrum: 5,
        price: 4,
        atmosphere: ["lively", "cozy"],
        desc: "편안한 맛을 제공. 공간이 넓고 쾌적해 여유로움.",
        oneLiner: "올드 스쿨 멜번 바이브. 편안하고 익숙한 맛.",
        tags: ["Nutty ⭐⭐⭐⭐⭐", "Relaxed"],
        image: "images/auction_rooms.jpg"
    },
    {
        name: "The Kettle Black",
        location: "South Melbourne",
        suburb: "South Melbourne",
        spectrum: 4,
        price: 4,
        atmosphere: ["modern", "unique"],
        desc: "고급스러운 인테리어. 정돈되고 깔끔한 고소함.",
        oneLiner: "눈과 입이 모두 즐거운, 가장 우아한 브런치 & 커피.",
        tags: ["Nutty ⭐⭐⭐⭐", "Elegant"],
        image: "images/the_kettle_black.jpg"
    }
];

document.addEventListener('DOMContentLoaded', () => {
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
            4: "🥜 고소함 & 부드러움 (Nutty/Smooth)",
            5: "🍫 묵직함 & 초콜릿 (Heavy/Dark)"
        };
        display.innerHTML = labels[val] || labels[3];
    }
    updateSliderLabel(slider.value);

    form.addEventListener('submit', (e) => {
        e.preventDefault();

        const tastePref = parseInt(slider.value);
        const selectedPrices = Array.from(document.querySelectorAll('input[name="price"]:checked')).map(cb => parseInt(cb.value));
        const atmosphere = document.getElementById('atmosphere').value;
        const location = document.getElementById('location').value;

        let suggestions = coffeeShops.filter(shop => {
            if (selectedPrices.length > 0 && !selectedPrices.includes(shop.price)) return false;
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
                    <h3>${shop.name}</h3>
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
