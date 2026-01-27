document.addEventListener("DOMContentLoaded", function () {

  /* =========================
     AVATAR DROPDOWN
  ========================== */
  const avatarBtn = document.getElementById("avatarBtn");
  const dropdownCard = document.getElementById("dropdownCard");

  if (avatarBtn && dropdownCard) {
    avatarBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      dropdownCard.classList.toggle("show");
    });

    document.addEventListener("click", () => {
      dropdownCard.classList.remove("show");
    });
  }

  /* =========================
     ACCOUNT MODAL
  ========================== */
  const accountModal = document.getElementById("accountModal");

  if (accountModal) {
    accountModal.addEventListener("click", function (e) {
      if (e.target === accountModal) {
        closeAccountModal();
      }
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeAccountModal();
      closeProfileEdit();
      closePasswordModal();
      closeDeleteModal();
    }
  });

  /* =========================
     DELETE ACCOUNT INPUT CHECK
  ========================== */
  const deleteInput = document.getElementById("deleteInput");
  const deleteBtn = document.getElementById("deleteBtn");

  if (deleteInput && deleteBtn) {
    deleteInput.addEventListener("input", function () {
      deleteBtn.disabled = deleteInput.value !== "Delete account";
    });
  }
});

/* =========================
   ACCOUNT MODAL FUNCTIONS
========================== */
function openAccountModal() {
  const dropdownCard = document.getElementById("dropdownCard");
  if (dropdownCard) dropdownCard.classList.remove("show");

  const modal = document.getElementById("accountModal");
  if (modal) modal.classList.add("show");
}

function closeAccountModal() {
  const modal = document.getElementById("accountModal");
  if (modal) modal.classList.remove("show");
}

/* =========================
   SIDEBAR TABS
========================== */
function showTab(tabId) {
  const profileTab = document.getElementById("profileTab");
  const securityTab = document.getElementById("securityTab");

  const btnProfile = document.getElementById("btnProfile");
  const btnSecurity = document.getElementById("btnSecurity");

  if (profileTab) profileTab.style.display = "none";
  if (securityTab) securityTab.style.display = "none";

  const activeTab = document.getElementById(tabId);
  if (activeTab) activeTab.style.display = "block";

  if (btnProfile) btnProfile.classList.remove("active");
  if (btnSecurity) btnSecurity.classList.remove("active");

  if (tabId === "profileTab" && btnProfile) btnProfile.classList.add("active");
  if (tabId === "securityTab" && btnSecurity) btnSecurity.classList.add("active");
}

/* =========================
   UPDATE PROFILE MODAL
========================== */
function openProfileEdit() {
  const modal = document.getElementById("profileEditModal");
  if (modal) modal.classList.add("show");
}

function closeProfileEdit() {
  const modal = document.getElementById("profileEditModal");
  if (modal) modal.classList.remove("show");
}

/* =========================
   CONNECTED ACCOUNT DOTS
========================== */
function toggleDots() {
  const menu = document.getElementById("dotsMenu");
  if (menu) menu.classList.toggle("show");
}

/* =========================
   SET PASSWORD MODAL
========================== */
function openPasswordModal() {
  const modal = document.getElementById("passwordModal");
  if (modal) modal.classList.add("show");
}

function closePasswordModal() {
  const modal = document.getElementById("passwordModal");
  if (modal) modal.classList.remove("show");
}

/* =========================
   DELETE ACCOUNT MODAL
========================== */
function openDeleteModal() {
  const modal = document.getElementById("deleteModal");
  if (modal) modal.classList.add("show");
}

function closeDeleteModal() {
  const modal = document.getElementById("deleteModal");
  if (modal) modal.classList.remove("show");
}
