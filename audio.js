(function () {
  "use strict";

  const audioPath = 'head_in_the_ceiling_fan.ogg';
  
  let audio1 = new Audio(audioPath);
  let audio2 = new Audio(audioPath);
  audio1.loop = false;
  audio2.loop = false;
  audio1.volume = 1.0;
  audio2.volume = 0.0;

  let activeAudio = audio1;
  let standbyAudio = audio2;
  let started = false;
  let isCrossfading = false;

  [audio1, audio2].forEach((aud, idx) => {
    aud.addEventListener('error', (e) => {
      console.error(`Audio ${idx + 1} failed to load. Check filename and upload:`, audioPath, e);
    });
  });

  function crossfade() {
    if (isCrossfading) return;
    isCrossfading = true;

    
    standbyAudio.currentTime = 0;
    standbyAudio.volume = 0.0;
    standbyAudio.play().catch(e => console.log("Crossfade play error:", e));

    const duration = 2000; 
    const steps = 20;
    const stepTime = duration / steps;
    let currentStep = 0;

    const fadeInterval = setInterval(() => {
      currentStep++;
      const progress = currentStep / steps;

      
      activeAudio.volume = Math.max(0, 1.0 - progress);
      standbyAudio.volume = Math.min(1.0, progress);

      if (currentStep >= steps) {
        clearInterval(fadeInterval);
        activeAudio.pause();
        
        
        const temp = activeAudio;
        activeAudio = standbyAudio;
        standbyAudio = temp;
        
        isCrossfading = false;
      }
    }, stepTime);
  }

  function triggerStart(e) {
    if (started) return;
    started = true;

    const overlay = document.getElementById("overlay");
    if (overlay) {
      overlay.classList.add("hidden");
    }

    const stage = document.getElementById("stage");
    if (stage) {
      if (stage.requestFullscreen) {
        stage.requestFullscreen().catch(err => console.log("Fullscreen error:", err));
      } else if (stage.webkitRequestFullscreen) {
        stage.webkitRequestFullscreen();
      } else if (stage.msRequestFullscreen) {
        stage.msRequestFullscreen();
      }
    }

    activeAudio.currentTime = 0;
    activeAudio.volume = 0.0;
    activeAudio.play().then(() => {
      
      let vol = 0;
      const fadeIn = setInterval(() => {
        vol += 0.1;
        activeAudio.volume = Math.min(1.0, vol);
        if (vol >= 1.0) clearInterval(fadeIn);
      }, 100);
    }).catch(err => console.log("Playback error:", err));

    if (window.__startExperience) {
      window.__startExperience();
    }
  }

  
  setInterval(() => {
    if (!started || isCrossfading) return;
    const timeLeft = activeAudio.duration - activeAudio.currentTime;
   
    if (!isNaN(timeLeft) && timeLeft <= 2.0 && activeAudio.currentTime > 2) {
      crossfade();
    }
  }, 250);

  window.__onAnimRestart = function() {
    activeAudio.pause();
    standbyAudio.pause();
    activeAudio.currentTime = 0;
    activeAudio.volume = 1.0;
    activeAudio.play().catch(e => {});
    isCrossfading = false;
  };

  window.addEventListener("DOMContentLoaded", () => {
    const stage = document.getElementById("stage");
    const playBtn = document.getElementById("playBtn");

    if (stage) stage.addEventListener("click", triggerStart);
    if (playBtn) playBtn.addEventListener("click", triggerStart);
    document.addEventListener("keydown", (ev) => {
      if (ev.code === "Space" || ev.code === "Enter") {
        triggerStart(ev);
      }
    });
  });
})();