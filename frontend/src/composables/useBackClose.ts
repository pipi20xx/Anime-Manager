import { watch, onMounted, onUnmounted, Ref } from 'vue'

/**
 * Enables Android Back Button (or Browser Back) to close a modal/ref.
 * 
 * @param isOpen - The boolean ref controlling the modal visibility.
 */
export function useBackClose(isOpen: Ref<boolean>) {
  // Track if the closure was triggered by the back button
  let isBackNav = false

  const handlePopState = (event: PopStateEvent) => {
    // If the modal is currently open and we receive a popstate (back button),
    // it means we are returning to the state *before* the modal was opened.
    if (isOpen.value) {
      isBackNav = true
      isOpen.value = false
    }
  }

  watch(isOpen, (val) => {
    if (val) {
      // Modal Opened: Push a generic state to history so we have something to pop
      isBackNav = false
      window.history.pushState({ modalOpen: true }, '')
    } else {
      // Modal Closed
      if (isBackNav) {
        // Closed via Back Button: State is already popped. Reset flag.
        isBackNav = false
      } else {
        // Closed via UI (e.g. Close button):
        // We need to pop the state we pushed when we opened it.
        // NOTE: This assumes the user hasn't navigated *forward* since opening the modal.
        // For standard modals, this is a safe assumption.
        window.history.back()
      }
    }
  })
  
  onMounted(() => {
    window.addEventListener('popstate', handlePopState)
  })

  onUnmounted(() => {
    window.removeEventListener('popstate', handlePopState)
  })
}
