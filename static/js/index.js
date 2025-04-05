document.addEventListener('DOMContentLoaded', () => {
  // Handle mobile navbar toggle
  const $navbarBurgers = Array.prototype.slice.call(document.querySelectorAll('.navbar-burger'), 0);
  if ($navbarBurgers.length > 0) {
    $navbarBurgers.forEach(el => {
      el.addEventListener('click', () => {
        const target = el.dataset.target;
        const $target = document.getElementById(target);
        el.classList.toggle('is-active');
        $target.classList.toggle('is-active');
      });
    });
  }

  // Initialize image modals if needed
  const images = document.querySelectorAll('.image-modal');
  images.forEach(image => {
    image.addEventListener('click', () => {
      const modal = document.getElementById(image.dataset.target);
      modal.classList.add('is-active');
    });
  });

  const closeModals = document.querySelectorAll('.modal-close, .modal-background');
  closeModals.forEach(close => {
    close.addEventListener('click', () => {
      const modal = close.closest('.modal');
      modal.classList.remove('is-active');
    });
  });

  // Make sure videos are responsive
  const videos = document.querySelectorAll('video');
  videos.forEach(video => {
    video.playbackRate = 1.0;
    video.play();
  });
});