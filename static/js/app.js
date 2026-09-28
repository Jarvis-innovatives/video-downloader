document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const urlInput = document.getElementById('urlInput');
  const pasteBtn = document.getElementById('pasteBtn');
  const fetchBtn = document.getElementById('fetchBtn');
  const fetchBtnText = document.getElementById('fetchBtnText');
  const fetchIcon = document.getElementById('fetchIcon');
  const errorMsg = document.getElementById('errorMsg');

  const resultSection = document.getElementById('resultSection');
  const thumbnailImg = document.getElementById('thumbnailImg');
  const videoPreview = document.getElementById('videoPreview');
  const playBtn = document.getElementById('playBtn');
  const durationBadge = document.getElementById('durationBadge');

  const platformBadge = document.getElementById('platformBadge');
  const videoTitle = document.getElementById('videoTitle');
  const videoChannel = document.getElementById('videoChannel');
  const videoViews = document.getElementById('videoViews');
  const videoDuration = document.getElementById('videoDuration');

  const formatVideoBtn = document.getElementById('formatVideoBtn');
  const formatMp3Btn = document.getElementById('formatMp3Btn');
  const qualityOptions = document.getElementById('qualityOptions');

  const downloadBtn = document.getElementById('downloadBtn');
  const downloadBtnText = document.getElementById('downloadBtnText');
  const progressContainer = document.getElementById('progressContainer');
  const progressLabel = document.getElementById('progressLabel');
  const progressPercent = document.getElementById('progressPercent');
  const progressBar = document.getElementById('progressBar');
  const doneContainer = document.getElementById('doneContainer');
  const doneFileName = document.getElementById('doneFileName');
  const resetBtn = document.getElementById('resetBtn');

  // Application State
  let currentMeta = null;
  let currentFormat = 'video';
  let currentQuality = '1080p';
  let isPlaying = false;
  let progressInterval = null;

  const DEFAULT_VIDEO_QUALITIES = ["240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"];
  const DEFAULT_MP3_QUALITIES = ["128 kbps", "192 kbps", "256 kbps", "320 kbps"];

  // Clipboard Paste
  if (pasteBtn) {
    pasteBtn.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          urlInput.value = text;
        }
      } catch (e) {
        console.warn('Clipboard access denied or unavailable.');
      }
    });
  }

  // Handle Enter Key inside URL Input
  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      handleFetch();
    }
  });

  fetchBtn.addEventListener('click', handleFetch);

  async function handleFetch() {
    const url = urlInput.value.trim();
    if (!url) {
      showError('Please paste a video link first.');
      return;
    }

    hideError();
    setFetchLoading(true);

    try {
      const response = await fetch('/api/fetch/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        showError(data.error || 'Could not process that video link.');
        setFetchLoading(false);
        return;
      }

      currentMeta = data;
      currentFormat = 'video';
      const vQuals = currentMeta.video_qualities || DEFAULT_VIDEO_QUALITIES;
      currentQuality = vQuals.includes('1080p') ? '1080p' : vQuals[vQuals.length - 1];

      updateResultCardUI();
      setFetchLoading(false);

      resultSection.classList.remove('hidden');
      resultSection.scrollIntoView({ behavior: 'smooth', block: 'center' });

    } catch (err) {
      console.error(err);
      showError('Network error — please make sure Django dev server is running.');
      setFetchLoading(false);
    }
  }

  function setFetchLoading(isLoading) {
    if (isLoading) {
      fetchBtn.disabled = true;
      fetchBtn.style.opacity = '0.7';
      fetchBtnText.textContent = 'Fetching…';
      fetchIcon.innerHTML = `<svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>`;
    } else {
      fetchBtn.disabled = false;
      fetchBtn.style.opacity = '1';
      fetchBtnText.textContent = 'Fetch';
      fetchIcon.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>`;
    }
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.classList.remove('hidden');
  }

  function hideError() {
    errorMsg.textContent = '';
    errorMsg.classList.add('hidden');
  }

  function updateResultCardUI() {
    if (!currentMeta) return;

    // Platform Badge
    platformBadge.textContent = currentMeta.platform;
    platformBadge.className = 'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ' +
      (currentMeta.platform === 'YouTube' ? 'platform-youtube' :
        currentMeta.platform === 'Instagram' ? 'platform-instagram' :
          currentMeta.platform === 'TikTok' ? 'platform-tiktok' : 'platform-moviebox');

    videoTitle.textContent = currentMeta.title;
    videoChannel.textContent = currentMeta.channel;
    videoViews.textContent = currentMeta.views;
    videoDuration.textContent = currentMeta.duration;
    durationBadge.textContent = currentMeta.duration;

    if (currentMeta.thumbnail_url) {
      thumbnailImg.src = currentMeta.thumbnail_url;
    }

    if (currentMeta.preview_url && videoPreview) {
      videoPreview.src = currentMeta.preview_url;
      if (playBtn) playBtn.classList.remove('hidden');
    } else {
      if (videoPreview) videoPreview.src = '';
      if (playBtn) playBtn.classList.add('hidden');
    }

    // Reset video player state on new fetch
    isPlaying = false;
    thumbnailImg.classList.remove('hidden');
    if (videoPreview) {
      videoPreview.classList.add('hidden');
      videoPreview.pause();
    }
    if (playBtn) playBtn.style.opacity = '1';

    renderFormatTabs();
    renderQualityButtons();
    updateDownloadButtonText();
    resetDownloadState();
  }

  function renderFormatTabs() {
    if (currentFormat === 'video') {
      formatVideoBtn.className = 'flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold bg-primary text-primary-foreground';
      formatMp3Btn.className = 'flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground';
    } else {
      formatMp3Btn.className = 'flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold bg-primary text-primary-foreground';
      formatVideoBtn.className = 'flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground';
    }
  }

  formatVideoBtn.addEventListener('click', () => {
    if (currentFormat !== 'video') {
      currentFormat = 'video';
      const vQuals = currentMeta && currentMeta.video_qualities ? currentMeta.video_qualities : DEFAULT_VIDEO_QUALITIES;
      currentQuality = vQuals.includes('1080p') ? '1080p' : vQuals[vQuals.length - 1];
      renderFormatTabs();
      renderQualityButtons();
      updateDownloadButtonText();
    }
  });

  formatMp3Btn.addEventListener('click', () => {
    if (currentFormat !== 'mp3') {
      currentFormat = 'mp3';
      const mQuals = currentMeta && currentMeta.mp3_qualities ? currentMeta.mp3_qualities : DEFAULT_MP3_QUALITIES;
      currentQuality = mQuals.includes('320 kbps') ? '320 kbps' : mQuals[mQuals.length - 1];
      renderFormatTabs();
      renderQualityButtons();
      updateDownloadButtonText();
    }
  });

  function renderQualityButtons() {
    qualityOptions.innerHTML = '';
    const qualities = currentFormat === 'video'
      ? (currentMeta && currentMeta.video_qualities ? currentMeta.video_qualities : DEFAULT_VIDEO_QUALITIES)
      : (currentMeta && currentMeta.mp3_qualities ? currentMeta.mp3_qualities : DEFAULT_MP3_QUALITIES);

    qualities.forEach((q) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      const isSelected = currentQuality === q;
      btn.className = `rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all ${isSelected
          ? 'border-primary bg-primary/15 text-primary'
          : 'border-border bg-background text-muted-foreground hover:border-input hover:text-foreground'
        }`;
      btn.innerHTML = q + (q === '2160p' ? ' <span class="ml-1 text-[10px]">4K</span>' : '');
      btn.addEventListener('click', () => {
        currentQuality = q;
        renderQualityButtons();
        updateDownloadButtonText();
      });
      qualityOptions.appendChild(btn);
    });
  }

  function updateDownloadButtonText() {
    if (currentFormat === 'video') {
      downloadBtnText.textContent = `Download Video · ${currentQuality}`;
    } else {
      downloadBtnText.textContent = `Download MP3 · ${currentQuality}`;
    }
  }

  function resetDownloadState() {
    downloadBtn.classList.remove('hidden');
    progressContainer.classList.add('hidden');
    doneContainer.classList.add('hidden');
    if (progressInterval) clearInterval(progressInterval);
  }

  // Handle Download Action
  downloadBtn.addEventListener('click', async () => {
    if (!currentMeta) return;

    hideError();
    downloadBtn.classList.add('hidden');
    progressContainer.classList.remove('hidden');
    progressLabel.textContent = `Connecting to server…`;
    progressBar.style.width = '0%';
    progressPercent.textContent = '0%';

    if (progressInterval) clearInterval(progressInterval);

    try {
      // 1. Initiate asynchronous download task on backend
      const startResponse = await fetch('/api/start_download/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: currentMeta.url,
          platform: currentMeta.platform,
          format: currentFormat,
          quality: currentQuality,
          title: currentMeta.title
        })
      });

      const startData = await startResponse.json();

      if (!startResponse.ok || !startData.success || !startData.task_id) {
        resetDownloadState();
        showError(startData.error || 'Failed to start download task.');
        return;
      }

      const taskId = startData.task_id;
      let isFetchingFile = false;

      // 2. Poll progress at fixed interval (300ms) for real-time byte updates
      progressInterval = setInterval(async () => {
        if (isFetchingFile) return;

        try {
          const progResponse = await fetch(`/api/progress/${taskId}/`);
          if (!progResponse.ok) return;

          const progData = await progResponse.json();
          if (!progData.success) return;

          const status = progData.status;

          if (status === 'starting') {
            progressBar.style.width = '0%';
            progressPercent.textContent = '0%';
            progressLabel.textContent = `Preparing ${currentFormat === 'video' ? 'video' : 'audio'} download…`;

          } else if (status === 'downloading') {
            const pct = Math.min(99, Math.round(progData.percent || 0));
            progressBar.style.width = `${pct}%`;
            progressPercent.textContent = `${pct}%`;

            const downloadedMB = (progData.downloaded_bytes / (1024 * 1024)).toFixed(1);
            if (progData.total_bytes > 0) {
              const totalMB = (progData.total_bytes / (1024 * 1024)).toFixed(1);
              progressLabel.textContent = `Downloaded: ${downloadedMB} MB / ${totalMB} MB → ${pct}%`;
            } else {
              progressLabel.textContent = `Downloaded: ${downloadedMB} MB → ${pct}%`;
            }

          } else if (status === 'processing') {
            progressBar.style.width = '99%';
            progressPercent.textContent = '99%';
            progressLabel.textContent = `Processing media (merging/converting)…`;

          } else if (status === 'completed') {
            clearInterval(progressInterval);
            isFetchingFile = true;

            progressBar.style.width = '100%';
            progressPercent.textContent = '100%';
            progressLabel.textContent = `Download complete! Saving file…`;

            // 3. Fetch completed file and trigger browser save
            const fileResponse = await fetch(`/api/get_file/${taskId}/`);
            if (!fileResponse.ok) {
              resetDownloadState();
              showError('Download finished, but file could not be retrieved from server.');
              return;
            }

            const disposition = fileResponse.headers.get('Content-Disposition');
            let filename = '';
            if (disposition && disposition.includes('filename=')) {
              const matches = /filename="?([^"]+)"?/.exec(disposition);
              if (matches && matches[1]) filename = matches[1];
            }

            if (!filename) {
              const cleanQ = currentQuality.replace(' ', '');
              const ext = currentFormat === 'video' ? 'mp4' : 'mp3';
              filename = `SnapGrab_${currentFormat}_${cleanQ}.${ext}`;
            }

            const blob = await fileResponse.blob();
            const blobUrl = URL.createObjectURL(blob);

            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);

            setTimeout(() => {
              progressContainer.classList.add('hidden');
              doneContainer.classList.remove('hidden');
              doneFileName.textContent = `${filename} saved to your device`;
            }, 300);

          } else if (status === 'error') {
            clearInterval(progressInterval);
            resetDownloadState();
            showError(progData.error || 'An error occurred during download.');
          }

        } catch (pollErr) {
          console.warn('Progress poll error:', pollErr);
        }
      }, 300);

    } catch (err) {
      console.error(err);
      if (progressInterval) clearInterval(progressInterval);
      resetDownloadState();
      showError('Network error during download initialization.');
    }
  });


  resetBtn.addEventListener('click', () => {
    urlInput.value = '';
    resultSection.classList.add('hidden');
    resetDownloadState();
    if (videoPreview) {
      videoPreview.pause();
      videoPreview.src = '';
    }
    currentMeta = null;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Play Button toggle for preview
  if (playBtn) {
    playBtn.addEventListener('click', () => {
      if (!currentMeta || !currentMeta.preview_url) return;
      isPlaying = !isPlaying;
      if (isPlaying) {
        thumbnailImg.classList.add('hidden');
        videoPreview.classList.remove('hidden');
        videoPreview.play().catch(err => console.warn('Preview playback error:', err));
        playBtn.style.opacity = '0.3';
      } else {
        videoPreview.pause();
        playBtn.style.opacity = '1';
      }
    });
  }
});
