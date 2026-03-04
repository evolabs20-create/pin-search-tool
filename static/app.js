const PinSearch = {
    selectedImageFile: null,
    collectionVisible: true,

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
            if (data.error) {
                this.showError(data.error);
            } else {
                this.renderResults(data.results, data.count);
                this.refreshHistory();
            }
        } catch (err) {
            this.showError('Image search failed. Please try again.');
        } finally {
            this.hideLoading();
        }
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
