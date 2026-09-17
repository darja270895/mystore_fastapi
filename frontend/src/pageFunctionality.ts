export const handleRefresh = () => {
    // Reloads the current page
    window.location.reload();
};

export function clearLocaltorage() {
    localStorage.removeItem('user')
    handleRefresh()
}