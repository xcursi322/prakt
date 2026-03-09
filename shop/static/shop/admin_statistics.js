(function () {
  const chartLabelsNode = document.getElementById('chart-labels');
  const visitsSeriesNode = document.getElementById('visits-series');
  const ordersSeriesNode = document.getElementById('orders-series');
  const revenueSeriesNode = document.getElementById('revenue-series');
  const statusLabelsNode = document.getElementById('status-labels');
  const statusValuesNode = document.getElementById('status-values');

  if (!chartLabelsNode || !visitsSeriesNode || !ordersSeriesNode || !revenueSeriesNode || !statusLabelsNode || !statusValuesNode) {
    return;
  }

  const chartLabels = JSON.parse(chartLabelsNode.textContent);
  const visitsSeries = JSON.parse(visitsSeriesNode.textContent);
  const ordersSeries = JSON.parse(ordersSeriesNode.textContent);
  const revenueSeries = JSON.parse(revenueSeriesNode.textContent);
  const statusLabels = JSON.parse(statusLabelsNode.textContent);
  const statusValues = JSON.parse(statusValuesNode.textContent);

  const visitsOrdersCanvas = document.getElementById('visitsOrdersChart');
  const revenueCanvas = document.getElementById('revenueChart');
  const statusCanvas = document.getElementById('statusChart');

  if (!visitsOrdersCanvas || !revenueCanvas || !statusCanvas || typeof Chart === 'undefined') {
    return;
  }

  new Chart(visitsOrdersCanvas, {
    type: 'line',
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: 'Відвідування',
          data: visitsSeries,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.15)',
          tension: 0.3,
          fill: true,
        },
        {
          label: 'Замовлення',
          data: ordersSeries,
          borderColor: '#16a34a',
          backgroundColor: 'rgba(22, 163, 74, 0.12)',
          tension: 0.3,
          fill: true,
        },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });

  new Chart(revenueCanvas, {
    type: 'bar',
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: 'Виручка, ₴',
          data: revenueSeries,
          backgroundColor: 'rgba(249, 115, 22, 0.6)',
          borderColor: '#f97316',
          borderWidth: 1,
        },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });

  new Chart(statusCanvas, {
    type: 'doughnut',
    data: {
      labels: statusLabels,
      datasets: [
        {
          data: statusValues,
          backgroundColor: ['#3b82f6', '#f59e0b', '#a855f7', '#22c55e', '#6b7280'],
        },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });
})();
