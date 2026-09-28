document.addEventListener('DOMContentLoaded', () => {
  const movieSearchInput = document.getElementById('movieSearchInput');
  const movieSearchBtn = document.getElementById('movieSearchBtn');
  const movieSearchStatus = document.getElementById('movieSearchStatus');
  const movieResultsGrid = document.getElementById('movieResultsGrid');
  const movieDetailCard = document.getElementById('movieDetailCard');

  const detailThumb = document.getElementById('detailThumb');
  const detailTitle = document.getElementById('detailTitle');
  const detailDuration = document.getElementById('detailDuration');
  const detailViews = document.getElementById('detailViews');

  const movieFormatVideoBtn = document.getElementById('movieFormatVideoBtn');
  const movieFormatMp3Btn = document.getElementById('movieFormatMp3Btn');
  const movieQualityOptions = document.getElementById('movieQualityOptions');

  const movieDownloadBtn = document.getElementById('movieDownloadBtn');
  const movieDownloadBtnText = document.getElementById('movieDownloadBtnText');
  const movieProgressContainer = document.getElementById('movieProgressContainer');
  const movieProgressLabel = document.getElementById('movieProgressLabel');
  const movieProgressPercent = document.getElementById('movieProgressPercent');
  const movieProgressBar = document.getElementById('movieProgressBar');
  const movieDoneContainer = document.getElementById('movieDoneContainer');
  const movieDoneFileName = document.getElementById('movieDoneFileName');

  let currentMovie = null;
  let currentFormat = 'video';
  let currentQuality = '1080p';
  let debounceTimer = null;
  let progressInterval = null;

  const DEFAULT_QUALITIES = ["480p", "720p", "1080p", "2160p"];
  const DEFAULT_MP3_QUALITIES = ["128 kbps", "192 kbps", "256 kbps", "320 kbps"];

  // Initial load: search default popular movies
  fetchMovieResults('Action Blockbuster');

  // Live input search as user types letters (300ms debounce)
  if (movieSearchInput) {
    movieSearchInput.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      if (debounceTimer) clearTimeout(debounceTimer);

      debounceTimer = setTimeout(() => {
        if (q.length > 0) {
          fetchMovieResults(q);
        } else {
          fetchMovieResults('Action Blockbuster');
        }
      }, 300);
    });

    movieSearchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const q = movieSearchInput.value.trim();
        fetchMovieResults(q || 'Action Blockbuster');
      }
    });
  }

  // Zoom Search Icon button click
  if (movieSearchBtn) {
    movieSearchBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const q = movieSearchInput ? movieSearchInput.value.trim() : '';
      fetchMovieResults(q || 'Action Blockbuster');
    });
  }

  async function fetchMovieResults(query) {
    if (movieSearchStatus) {
      movieSearchStatus.classList.remove('hidden');
      movieSearchStatus.textContent = `Searching MovieBox for "${query}"…`;
    }

    try {
      const res = await fetch(`/api/search_movies/?q=${encodeURIComponent(query)}`);
      const data = await res.json();

      if (movieSearchStatus) {
        movieSearchStatus.classList.add('hidden');
      }

      if (!res.ok || !data.success || !data.movies) {
        movieResultsGrid.innerHTML = `<div class="col-span-full text-center text-muted-foreground py-8">No movies found matching "${query}".</div>`;
        return;
      }

      renderMovieCards(data.movies);

    } catch (err) {
      console.error(err);
      if (movieSearchStatus) {
        movieSearchStatus.classList.remove('hidden');
        movieSearchStatus.textContent = 'Error connecting to MovieBox server.';
      }
    }
  }

  function renderMovieCards(movies) {
    movieResultsGrid.innerHTML = '';

    if (!movies || movies.length === 0) {
      movieResultsGrid.innerHTML = `<div class="col-span-full text-center text-muted-foreground py-8">No movies found.</div>`;
      return;
    }

    movies.forEach(movie => {
      const card = document.createElement('div');
      card.className = 'moviebox-card';
      const thumb = movie.thumbnail_url || '/static/media/sample-thumb.jpg';

      card.innerHTML = `
        <div class="moviebox-poster-wrap">
          <img src="${thumb}" alt="${movie.title}" class="moviebox-poster-img" onerror="this.src='/static/media/sample-thumb.jpg'" />
          <div class="moviebox-overlay">
            <div class="moviebox-zoom-icon" title="View & Download">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <circle cx="11" cy="11" r="7"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </div>
          </div>
        </div>
        <div class="moviebox-card-content">
          <h4 class="moviebox-card-title">${movie.title}</h4>
          <div class="moviebox-card-meta">
            <span>${movie.duration || 'Full Movie'}</span>
            <span class="moviebox-badge">MovieBox HD</span>
          </div>
        </div>
      `;

      card.addEventListener('click', () => {
        selectMovie(movie);
      });

      movieResultsGrid.appendChild(card);
    });
  }

  function selectMovie(movie) {
    currentMovie = movie;
    currentFormat = 'video';
    const quals = movie.video_qualities || DEFAULT_QUALITIES;
    currentQuality = quals.includes('1080p') ? '1080p' : quals[quals.length - 1];

    detailThumb.src = movie.thumbnail_url || '/static/media/sample-thumb.jpg';
    detailTitle.textContent = movie.title;
    detailDuration.textContent = movie.duration || 'Full Movie';
    detailViews.textContent = movie.views || 'MovieBox Stream';

    renderFormatTabs();
    renderQualityButtons();
    updateDownloadButtonText();
    resetDownloadState();

    movieDetailCard.classList.remove('hidden');
    movieDetailCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function renderFormatTabs() {
    if (currentFormat === 'video') {
      movieFormatVideoBtn.className = 'flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold bg-primary text-primary-foreground';
      movieFormatMp3Btn.className = 'flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground';
    } else {
      movieFormatMp3Btn.className = 'flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold bg-primary text-primary-foreground';
      movieFormatVideoBtn.className = 'flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground';
    }
  }

  movieFormatVideoBtn.addEventListener('click', () => {
    if (currentFormat !== 'video') {
      currentFormat = 'video';
      const quals = currentMovie && currentMovie.video_qualities ? currentMovie.video_qualities : DEFAULT_QUALITIES;
      currentQuality = quals.includes('1080p') ? '1080p' : quals[quals.length - 1];
      renderFormatTabs();
      renderQualityButtons();
      updateDownloadButtonText();
    }
  });

  movieFormatMp3Btn.addEventListener('click', () => {
    if (currentFormat !== 'mp3') {
      currentFormat = 'mp3';
      const quals = currentMovie && currentMovie.mp3_qualities ? currentMovie.mp3_qualities : DEFAULT_MP3_QUALITIES;
      currentQuality = quals.includes('320 kbps') ? '320 kbps' : quals[quals.length - 1];
      renderFormatTabs();
      renderQualityButtons();
      updateDownloadButtonText();
    }
  });

  function renderQualityButtons() {
    movieQualityOptions.innerHTML = '';
    const qualities = currentFormat === 'video'
      ? (currentMovie && currentMovie.video_qualities ? currentMovie.video_qualities : DEFAULT_QUALITIES)
      : (currentMovie && currentMovie.mp3_qualities ? currentMovie.mp3_qualities : DEFAULT_MP3_QUALITIES);

    qualities.forEach(q => {
      const btn = document.createElement('button');
      btn.type = 'button';
      const isSelected = currentQuality === q;
      btn.className = `rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all ${
        isSelected
          ? 'border-primary bg-primary/15 text-primary'
          : 'border-border bg-background text-muted-foreground hover:border-input hover:text-foreground'
      }`;
      btn.innerHTML = q + (q === '2160p' ? ' <span class="ml-1 text-[10px]">4K</span>' : '');
      btn.addEventListener('click', () => {
        currentQuality = q;
        renderQualityButtons();
        updateDownloadButtonText();
      });
      movieQualityOptions.appendChild(btn);
    });
  }

  function updateDownloadButtonText() {
    if (currentFormat === 'video') {
      movieDownloadBtnText.textContent = `Download Movie · ${currentQuality}`;
    } else {
      movieDownloadBtnText.textContent = `Download MP3 · ${currentQuality}`;
    }
  }

  function resetDownloadState() {
    movieDownloadBtn.classList.remove('hidden');
    movieProgressContainer.classList.add('hidden');
    movieDoneContainer.classList.add('hidden');
    if (progressInterval) clearInterval(progressInterval);
  }

  // Handle Movie Download Action
  movieDownloadBtn.addEventListener('click', async () => {
    if (!currentMovie) return;

    movieDownloadBtn.classList.add('hidden');
    movieProgressContainer.classList.remove('hidden');
    movieProgressLabel.textContent = `Connecting to MovieBox server…`;
    movieProgressBar.style.width = '0%';
    movieProgressPercent.textContent = '0%';

    if (progressInterval) clearInterval(progressInterval);

    try {
      // 1. Start task on backend
      const startRes = await fetch('/api/start_download/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: currentMovie.url,
          platform: 'MovieBox',
          format: currentFormat,
          quality: currentQuality,
          title: currentMovie.title
        })
      });

      const startData = await startRes.json();
      if (!startRes.ok || !startData.success || !startData.task_id) {
        resetDownloadState();
        alert(startData.error || 'Failed to start movie download.');
        return;
      }

      const taskId = startData.task_id;
      let isFetchingFile = false;

      // 2. Poll real progress (300ms)
      progressInterval = setInterval(async () => {
        if (isFetchingFile) return;

        try {
          const progRes = await fetch(`/api/progress/${taskId}/`);
          if (!progRes.ok) return;

          const progData = await progRes.json();
          if (!progData.success) return;

          const status = progData.status;

          if (status === 'starting') {
            movieProgressBar.style.width = '0%';
            movieProgressPercent.textContent = '0%';
            movieProgressLabel.textContent = `Initializing MovieBox stream…`;

          } else if (status === 'downloading') {
            const pct = Math.min(99, Math.round(progData.percent || 0));
            movieProgressBar.style.width = `${pct}%`;
            movieProgressPercent.textContent = `${pct}%`;

            const downloadedMB = (progData.downloaded_bytes / (1024 * 1024)).toFixed(1);
            if (progData.total_bytes > 0) {
              const totalMB = (progData.total_bytes / (1024 * 1024)).toFixed(1);
              movieProgressLabel.textContent = `Downloaded: ${downloadedMB} MB / ${totalMB} MB → ${pct}%`;
            } else {
              movieProgressLabel.textContent = `Downloaded: ${downloadedMB} MB → ${pct}%`;
            }

          } else if (status === 'processing') {
            movieProgressBar.style.width = '99%';
            movieProgressPercent.textContent = '99%';
            movieProgressLabel.textContent = `Processing movie stream…`;

          } else if (status === 'completed') {
            clearInterval(progressInterval);
            isFetchingFile = true;

            movieProgressBar.style.width = '100%';
            movieProgressPercent.textContent = '100%';
            movieProgressLabel.textContent = `Movie download complete! Saving file…`;

            // 3. Fetch completed file
            const fileRes = await fetch(`/api/get_file/${taskId}/`);
            if (!fileRes.ok) {
              resetDownloadState();
              alert('Movie download finished, but file could not be retrieved.');
              return;
            }

            const disposition = fileRes.headers.get('Content-Disposition');
            let filename = '';
            if (disposition && disposition.includes('filename=')) {
              const matches = /filename="?([^"]+)"?/.exec(disposition);
              if (matches && matches[1]) filename = matches[1];
            }

            if (!filename) {
              const cleanQ = currentQuality.replace(' ', '');
              const ext = currentFormat === 'video' ? 'mp4' : 'mp3';
              filename = `MovieBox_${currentMovie.title.replace(/\s+/g, '_')}_${cleanQ}.${ext}`;
            }

            const blob = await fileRes.blob();
            const blobUrl = URL.createObjectURL(blob);

            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);

            setTimeout(() => {
              movieProgressContainer.classList.add('hidden');
              movieDoneContainer.classList.remove('hidden');
              movieDoneFileName.textContent = `${filename} saved to your device`;
            }, 300);

          } else if (status === 'error') {
            clearInterval(progressInterval);
            resetDownloadState();
            alert(progData.error || 'Download failed.');
          }

        } catch (pollErr) {
          console.warn('Poll error:', pollErr);
        }
      }, 300);

    } catch (err) {
      console.error(err);
      if (progressInterval) clearInterval(progressInterval);
      resetDownloadState();
      alert('Network error during movie download.');
    }
  });
});
