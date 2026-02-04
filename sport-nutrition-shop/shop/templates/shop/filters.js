document.addEventListener('DOMContentLoaded', function() {
    const categoryFilter = document.getElementById('categoryFilter');
    const sortFilter = document.getElementById('sortFilter');

    if (categoryFilter) {
        categoryFilter.addEventListener('change', applyFilters);
    }

    if (sortFilter) {
        sortFilter.addEventListener('change', applyFilters);
    }

    function applyFilters() {
        const categoryId = categoryFilter ? categoryFilter.value : '';
        const sortValue = sortFilter ? sortFilter.value : '';
        let url = window.location.pathname;
        const params = new URLSearchParams();

        if (categoryId) params.append('category', categoryId);
        if (sortValue) params.append('sort', sortValue);

        if (params.toString()) {
            url += '?' + params.toString();
        }

        window.location.href = url;
    }
});
