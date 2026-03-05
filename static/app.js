const PinSearch = {
    selectedImageFile: null,
    collectionVisible: true,
    researchData: null,
    researchDetailsVisible: true,

    // === Init ===

    init() {
        this.initDragDrop();
        this.renderHistory(initialHistory || []);
        this.loadCollection();
    },

    // === Tabs ===

    switchTab(tabName) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        document.getElementById(`panel-${tabName}`).classList.add('active');
    },

    // === Drag & Drop ===

    initDragDrop() {
        const zone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('image-input');

        ['dragenter', 'dragover'].forEach(evt => {
            zone.addEventListener(evt, e => {
                e.preventDefault();
                zone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(evt => {
            zone.addEventListener(evt, e => {
                e.preventDefault();
                zone.classList.remove('drag-over');
            });
        });

        zone.addEventListener('drop', e => {
            const files = e.dataTransfer.files;
            if (files.length > 0) this.handleImageFile(files[0]);
        });

        zone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) this.handleImageFile(fileInput.files[0]);
        });
    },

    handleImageFile(file) {
        if (!file.type.startsWith('image/')) {
            this.showError('Please upload an image file (JPG, PNG, etc.)');
            return;
        }
        this.selectedImageFile = file;
        this.showImagePreview(file);
        document.getElementById('btn-image-search').style.display = 'block';
    },

    showImagePreview(file) {
        const preview = document.getElementById('image-preview');
        const reader = new FileReader();
        reader.onload = e => {
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    },

    // === Search Operations ===

    async searchByKeyword() {
        const query = document.getElementById('keyword-input').value.trim();
        if (!query) return;

        const source = this.getSource();
        this.showLoading();
        this.hideError();

        try {
            const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}&source=${source}`);
            const data = await resp.json();
            if (data.error) {
                this.showError(data.error);
            } else {
                this.renderResults(data.results, data.count);
                this.refreshHistory();
            }
        } catch (err) {
            this.showError('Search failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    },

    async lookupByNumber() {
        const pinNumber = document.getElementById('pin-number-input').value.trim();
        if (!pinNumber) return;

        const source = this.getSource();
        this.showLoading();
        this.hideError();

        try {
            const resp = await fetch(`/api/lookup?pin_number=${encodeURIComponent(pinNumber)}&source=${source}`);
            const data = await resp.json();
            if (data.error) {
                this.showError(data.error);
            } else {
                this.renderResults(data.results, data.count);
                this.refreshHistory();
            }
        } catch (err) {
            this.showError('Lookup failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    },

    async searchByImage() {
        if (!this.selectedImageFile) {
            this.showError('Please select or drop an image first.');
            return;
        }

        const source = this.getSource();
        const formData = new FormData();
        formData.append('image', this.selectedImageFile);
        formData.append('source', source);

        this.showLoading();
        this.hideError();

        try {
            const resp = await fetch('/api/image-search', {
                method: 'POST',
                body: formData,
            });
            const data = await resp.json();
            if (data.error && !data.results) {
                this.showError(data.error);
            } else {
                // Show AI identification info if available
                if (data.identification) {
                    this.showIdentification(data.identification, data.queries_used);
                }
                this.renderResults(data.results || [], data.count || 0);
                this.refreshHistory();
            }
        } catch (err) {
            this.showError('Image search failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    },

    showIdentification(info, queries) {
        let el = document.getElementById('identification-info');
        if (!el) {
            el = document.createElement('div');
            el.id = 'identification-info';
            el.className = 'identification-info';
            const results = document.getElementById('results-section');
            results.parentNode.insertBefore(el, results);
        }

        const chars = (info.characters || []).join(', ') || 'Unknown';
        const theme = info.theme || '';
        const desc = info.description || '';
        const edition = info.edition || '';
        const queriesHtml = (queries || []).map(q => `<span class="query-tag">${this.escapeHtml(q)}</span>`).join(' ');

        el.innerHTML = `
            <h3>AI Pin Identification</h3>
            <p class="id-description">${this.escapeHtml(desc)}</p>
            <div class="id-details">
                ${chars ? `<span><strong>Characters:</strong> ${this.escapeHtml(chars)}</span>` : ''}
                ${theme ? `<span><strong>Theme:</strong> ${this.escapeHtml(theme)}</span>` : ''}
                ${edition ? `<span><strong>Edition:</strong> ${this.escapeHtml(edition)}</span>` : ''}
                ${info.year ? `<span><strong>Year:</strong> ${this.escapeHtml(info.year)}</span>` : ''}
                ${info.origin ? `<span><strong>Origin:</strong> ${this.escapeHtml(info.origin)}</span>` : ''}
            </div>
            ${queriesHtml ? `<div class="id-queries"><strong>Searched for:</strong> ${queriesHtml}</div>` : ''}
            ${queries && queries.length > 0 ? `<button class="btn-research-bridge" onclick="PinSearch.startResearchFromImage('${this.escapeAttr(queries[0])}')">Research Prices on eBay</button>` : ''}
        `;
        el.style.display = 'block';
    },

    getSource() {
        const checked = document.querySelector('input[name="source"]:checked');
        return checked ? checked.value : 'all';
    },

    // === Results Rendering ===

    renderResults(pins, count) {
        const section = document.getElementById('results-section');
        const grid = document.getElementById('results-grid');
        const countEl = document.getElementById('result-count');

        if (!pins || pins.length === 0) {
            section.style.display = 'block';
            grid.innerHTML = '<p style="color: var(--gray); grid-column: 1/-1; text-align: center; padding: 2rem;">No pins found. Try a different search.</p>';
            countEl.textContent = '0 results';
            return;
        }

        countEl.textContent = `${count} result${count !== 1 ? 's' : ''}`;
        grid.innerHTML = '';

        pins.forEach((pin, i) => {
            const card = this.createPinCard(pin, false, i);
            grid.appendChild(card);
        });

        section.style.display = 'block';
    },

    createPinCard(pin, isCollection, index) {
        const card = document.createElement('div');
        card.className = 'pin-card';
        card.style.animationDelay = `${(index || 0) * 0.05}s`;

        const imgHtml = pin.image_url
            ? `<div class="pin-card-image"><img src="${this.escapeHtml(pin.image_url)}" alt="${this.escapeHtml(pin.name)}" loading="lazy" onerror="this.parentElement.classList.add('no-image'); this.replaceWith(document.createTextNode('No Image'))"></div>`
            : `<div class="pin-card-image no-image"><span>No Image</span></div>`;

        const badgeClass = (pin.source || '').includes('PinPics') ? 'badge-pinpics' : 'badge-pintradingdb';

        let metaHtml = '';
        if (pin.year || pin.edition_size) {
            metaHtml = '<div class="pin-meta">';
            if (pin.year) metaHtml += `<span>${this.escapeHtml(pin.year)}</span>`;
            if (pin.edition_size) metaHtml += `<span>${this.escapeHtml(pin.edition_size)}</span>`;
            metaHtml += '</div>';
        }

        let actionBtn;
        if (isCollection) {
            actionBtn = `<button class="btn-remove" onclick="PinSearch.removeFromCollection(${pin.id}, this)">Remove</button>`;
        } else if (pin.in_collection) {
            actionBtn = `<button class="btn-saved">Saved</button>`;
        } else {
            const pinJson = this.escapeAttr(JSON.stringify(pin));
            actionBtn = `<button class="btn-save" onclick="PinSearch.saveToCollection(${pinJson}, this)">Save</button>`;
        }

        const sourceLink = pin.source_url
            ? `<a href="${this.escapeHtml(pin.source_url)}" target="_blank" class="badge ${badgeClass}">${this.escapeHtml(pin.source)}</a>`
            : `<span class="badge ${badgeClass}">${this.escapeHtml(pin.source || 'Unknown')}</span>`;

        card.innerHTML = `
            ${imgHtml}
            <div class="pin-card-body">
                <h3 class="pin-name">${this.escapeHtml(pin.name)}</h3>
                ${pin.pin_number ? `<p class="pin-number">#${this.escapeHtml(pin.pin_number)}</p>` : ''}
                ${pin.series ? `<p class="pin-detail">${this.escapeHtml(pin.series)}</p>` : ''}
                ${metaHtml}
                <div class="pin-card-footer">
                    ${sourceLink}
                    ${actionBtn}
                </div>
            </div>
        `;
        return card;
    },

    // === Price Research ===

    async runResearch() {
        const query = document.getElementById('research-input').value.trim();
        if (!query) return;

        this.showLoading();
        this.hideError();
        document.getElementById('research-section').style.display = 'none';

        try {
            const resp = await fetch(`/api/research?q=${encodeURIComponent(query)}`);
            const data = await resp.json();
            if (data.error) {
                this.showError(data.error);
            } else {
                this.researchData = { query, ...data };
                this.renderResearch(data);
            }
        } catch (err) {
            this.showError('Price research failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    },

    renderResearch(data) {
        const section = document.getElementById('research-section');
        const summaryEl = document.getElementById('research-summary');
        const tbody = document.getElementById('research-table-body');
        const countEl = document.getElementById('research-detail-count');
        const s = data.summary;

        // Summary cards
        const fmtPrice = (v) => v != null ? `$${Number(v).toFixed(2)}` : 'N/A';

        summaryEl.innerHTML = `
            <div class="research-card research-card-active">
                <h4>Active Listings</h4>
                <div class="research-stat-big">${s.active_count}</div>
                <div class="research-stats">
                    <div><span class="stat-label">Low</span><span class="stat-value">${fmtPrice(s.active_low)}</span></div>
                    <div><span class="stat-label">High</span><span class="stat-value">${fmtPrice(s.active_high)}</span></div>
                    <div><span class="stat-label">Avg</span><span class="stat-value">${fmtPrice(s.active_avg)}</span></div>
                </div>
                ${s.cheapest_active_url ? `<a href="${this.escapeHtml(s.cheapest_active_url)}" target="_blank" class="research-link">View Cheapest</a>` : ''}
            </div>
            <div class="research-card research-card-sold">
                <h4>Sold (Last 90 Days)</h4>
                <div class="research-stat-big">${s.sold_count}</div>
                <div class="research-stats">
                    <div><span class="stat-label">Low</span><span class="stat-value">${fmtPrice(s.sold_low)}</span></div>
                    <div><span class="stat-label">High</span><span class="stat-value">${fmtPrice(s.sold_high)}</span></div>
                    <div><span class="stat-label">Avg</span><span class="stat-value">${fmtPrice(s.sold_avg)}</span></div>
                </div>
                ${s.last_sold_date ? `<div class="research-last-sold">Last sold: ${this.escapeHtml(s.last_sold_date)}</div>` : ''}
                ${s.most_recent_sold_url ? `<a href="${this.escapeHtml(s.most_recent_sold_url)}" target="_blank" class="research-link">View Most Recent</a>` : ''}
            </div>
        `;

        // Detail table
        const allListings = [
            ...(data.active_listings || []).map(l => ({ ...l, _type: 'active' })),
            ...(data.sold_listings || []).map(l => ({ ...l, _type: 'sold' })),
        ];
        countEl.textContent = `${allListings.length} listing${allListings.length !== 1 ? 's' : ''}`;

        tbody.innerHTML = '';
        allListings.forEach(l => {
            const tr = document.createElement('tr');
            const badge = l._type === 'active'
                ? '<span class="badge-active">Active</span>'
                : '<span class="badge-sold">Sold</span>';
            const date = l._type === 'sold' ? (l.sold_date || '') : (l.end_date || '');
            const titleLink = l.ebay_url
                ? `<a href="${this.escapeHtml(l.ebay_url)}" target="_blank">${this.escapeHtml(l.title)}</a>`
                : this.escapeHtml(l.title);

            tr.innerHTML = `
                <td>${badge}</td>
                <td class="research-title-cell">${titleLink}</td>
                <td>$${Number(l.price).toFixed(2)}</td>
                <td>${l.shipping_cost != null ? '$' + Number(l.shipping_cost).toFixed(2) : 'N/A'}</td>
                <td>${this.escapeHtml(l.condition || 'N/A')}</td>
                <td>${this.escapeHtml(l.seller_name || 'N/A')}</td>
                <td>${this.escapeHtml(date)}</td>
            `;
            tbody.appendChild(tr);
        });

        section.style.display = 'block';
    },

    toggleResearchDetails() {
        const wrap = document.getElementById('research-table-wrap');
        const arrow = document.getElementById('research-detail-arrow');
        this.researchDetailsVisible = !this.researchDetailsVisible;
        wrap.style.display = this.researchDetailsVisible ? 'block' : 'none';
        arrow.classList.toggle('collapsed', !this.researchDetailsVisible);
    },

    exportResearchCSV() {
        if (!this.researchData) return;
        window.location.href = `/api/research/export/csv?q=${encodeURIComponent(this.researchData.query)}`;
    },

    async exportResearchSheets() {
        if (!this.researchData) return;

        try {
            const resp = await fetch('/api/research/export/sheets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ q: this.researchData.query }),
            });
            const data = await resp.json();
            if (data.url) {
                window.open(data.url, '_blank');
            } else {
                this.showError(data.error || 'Google Sheets export failed.');
            }
        } catch (err) {
            this.showError('Google Sheets export failed. Check server configuration.');
        }
    },

    startResearchFromImage(query) {
        this.switchTab('research');
        document.getElementById('research-input').value = query;
        this.runResearch();
    },

    // === Collection ===

    async loadCollection() {
        try {
            const resp = await fetch('/api/collection');
            const data = await resp.json();
            this.renderCollection(data.pins || []);
        } catch (err) {
            console.error('Failed to load collection:', err);
        }
    },

    renderCollection(pins) {
        const grid = document.getElementById('collection-grid');
        const countEl = document.getElementById('collection-count');
        countEl.textContent = `${pins.length} pin${pins.length !== 1 ? 's' : ''}`;

        if (pins.length === 0) {
            grid.innerHTML = '<p style="color: var(--gray); grid-column: 1/-1; text-align: center; padding: 2rem;">No pins saved yet. Search and save pins to build your collection.</p>';
            return;
        }

        grid.innerHTML = '';
        pins.forEach((pin, i) => {
            grid.appendChild(this.createPinCard(pin, true, i));
        });
    },

    async saveToCollection(pinData, btn) {
        try {
            const resp = await fetch('/api/collection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pinData),
            });
            const data = await resp.json();
            if (data.id) {
                btn.className = 'btn-saved';
                btn.textContent = 'Saved';
                btn.onclick = null;
                btn.style.cursor = 'default';
                this.loadCollection();
            }
        } catch (err) {
            console.error('Failed to save pin:', err);
        }
    },

    async removeFromCollection(id, btn) {
        try {
            const resp = await fetch(`/api/collection/${id}`, { method: 'DELETE' });
            const data = await resp.json();
            if (!data.error) {
                this.loadCollection();
            }
        } catch (err) {
            console.error('Failed to remove pin:', err);
        }
    },

    toggleCollection() {
        const grid = document.getElementById('collection-grid');
        const arrow = document.getElementById('collection-arrow');
        this.collectionVisible = !this.collectionVisible;
        grid.style.display = this.collectionVisible ? 'grid' : 'none';
        arrow.classList.toggle('collapsed', !this.collectionVisible);
    },

    exportCollection() {
        window.location.href = '/api/collection/export';
    },

    // === Search History ===

    async refreshHistory() {
        try {
            const resp = await fetch('/api/history');
            const data = await resp.json();
            this.renderHistory(data.history || []);
        } catch (err) {
            console.error('Failed to load history:', err);
        }
    },

    renderHistory(entries) {
        const list = document.getElementById('history-list');

        if (!entries || entries.length === 0) {
            list.innerHTML = '<p style="color: var(--gray); font-size: 0.8rem; padding: 0.5rem;">No searches yet.</p>';
            return;
        }

        list.innerHTML = '';
        entries.forEach(entry => {
            const icons = { keyword: '\uD83D\uDD0D', lookup: '#', image: '\uD83D\uDCF7' };
            const icon = icons[entry.search_type] || '\uD83D\uDD0D';

            const item = document.createElement('div');
            item.className = 'history-item';
            item.onclick = () => this.replaySearch(entry);

            item.innerHTML = `
                <span class="history-icon">${icon}</span>
                <span class="history-text">${this.escapeHtml(entry.query)}</span>
                <span class="history-count">${entry.result_count}</span>
            `;
            list.appendChild(item);
        });
    },

    replaySearch(entry) {
        if (entry.search_type === 'keyword') {
            document.getElementById('keyword-input').value = entry.query;
            this.switchTab('keyword');
            this.searchByKeyword();
        } else if (entry.search_type === 'lookup') {
            document.getElementById('pin-number-input').value = entry.query;
            this.switchTab('lookup');
            this.lookupByNumber();
        }
        // Image searches can't be replayed (file is gone)
    },

    async clearHistory() {
        try {
            await fetch('/api/history', { method: 'DELETE' });
            this.renderHistory([]);
        } catch (err) {
            console.error('Failed to clear history:', err);
        }
    },

    // === UI Helpers ===

    showLoading() {
        document.getElementById('loading').style.display = 'block';
        document.getElementById('results-section').style.display = 'none';
        document.getElementById('research-section').style.display = 'none';
        const idPanel = document.getElementById('identification-info');
        if (idPanel) idPanel.style.display = 'none';
    },

    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    },

    showError(msg) {
        const el = document.getElementById('error-msg');
        el.textContent = msg;
        el.style.display = 'block';
    },

    hideError() {
        document.getElementById('error-msg').style.display = 'none';
    },

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    escapeAttr(str) {
        return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },
};

document.addEventListener('DOMContentLoaded', () => PinSearch.init());
