// Fonte e cores do padrão visual nos gráficos do Chart.js
if (window.Chart) {
    Chart.defaults.font.family = '"Inter", ui-sans-serif, system-ui, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = "#64748b";
    Chart.defaults.borderColor = "#e2e8f0";
    Chart.defaults.elements.bar.borderRadius = 4;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.tooltip.backgroundColor = "#0f172a";
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
}
