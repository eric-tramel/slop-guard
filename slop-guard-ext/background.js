// Background service worker — sets up right-click context menu
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "slop-guard-check",
    title: "Check with Slop Guard",
    contexts: ["selection"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "slop-guard-check" && info.selectionText) {
    // Store selected text, popup will read it
    chrome.storage.local.set({ pendingText: info.selectionText });
    // Open the popup programmatically isn't possible in MV3,
    // so we'll use a badge to indicate pending text
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#e94560" });
  }
});
