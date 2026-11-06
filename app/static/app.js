const SVG_NS = "http://www.w3.org/2000/svg";
const money = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", minimumFractionDigits: 2 });
const number = (decimals) =>
  new Intl.NumberFormat("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: decimals });
const kwh = new Intl.NumberFormat("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 3 });
const rate = number(4);
const amount = new Intl.NumberFormat("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const CONCEPTS = {
  EA: { name: "Energía activa", formula: "Consumo × CU", kind: "grid" },
  EC: { name: "Comercialización de excedentes", formula: "Inyección × C", kind: "supply" },
  EE1: { name: "Excedentes tipo 1", formula: "min(inyección, consumo) × (−CU)", kind: "supply" },
  EE2: { name: "Excedentes tipo 2", formula: "−Σ exceso de la hora × precio de bolsa", kind: "supply" },
};

function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  node.append(...children);
  return node;
}

function svg(tag, attributes = {}, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

// Las fechas de la API no tienen zona horaria: se tratan como UTC para mostrarlas tal cual.
function formatHour(value) {
  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);
  return new Intl.DateTimeFormat("es-CO", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC",
  }).format(date);
}

function monthName(month) {
  const [year, monthNumber] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("es-CO", { month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(year, monthNumber - 1, 1)));
}

/* Portada: curva del mes */

const hero = { service: null, id: null, hour: 719, animation: null };
const curveNode = document.getElementById("curve");
const scrub = document.getElementById("scrub");
const reading = document.getElementById("reading");
const digitsNode = document.getElementById("meter-digits");

function hourTimestamp(service, hour) {
  return new Date(Date.parse(`${service.start}Z`) + hour * 3_600_000).toISOString().slice(0, 19);
}

function renderDigits(value) {
  const [integer, decimals] = value.toFixed(2).split(".");
  digitsNode.replaceChildren(
    ...integer.padStart(5, "0").split("").map((digit) => el("span", { class: "digit" }, digit)),
    el("span", { class: "meter-separator" }, ","),
    ...decimals.split("").map((digit) => el("span", { class: "digit decimal" }, digit)),
  );
}

function curveGeometry() {
  const { service } = hero;
  const width = curveNode.clientWidth;
  const height = curveNode.clientHeight;
  const margin = { top: 34, right: 12, bottom: 26, left: 12 };
  const consumption = service.invoice.consumption_kwh;
  const values = service.accumulated_kwh;
  const injection = values[values.length - 1];
  // Si el consumo es mucho mayor, en su escala la curva se vería como una línea plana.
  const offScale = consumption > injection * 5;
  const top = offScale ? injection * 1.25 : Math.max(consumption, injection) * 1.1;
  const x = (hour) => margin.left + (hour / (values.length - 1)) * (width - margin.left - margin.right);
  const y = (value) => height - margin.bottom - (value / top) * (height - margin.top - margin.bottom);
  return { width, height, margin, consumption, injection, offScale, values, x, y };
}

function areaPath({ values, x, y }, lower, upper, end) {
  const forward = [];
  const backward = [];
  for (let hour = 0; hour <= end; hour += 1) {
    forward.push(`${x(hour).toFixed(1)},${y(upper(values[hour])).toFixed(1)}`);
    backward.unshift(`${x(hour).toFixed(1)},${y(lower(values[hour])).toFixed(1)}`);
  }
  return `M${forward.join("L")}L${backward.join("L")}Z`;
}

function renderCurve() {
  const { service, hour } = hero;
  if (!service) return;
  const geometry = curveGeometry();
  const { width, height, margin, consumption, injection, offScale, values, x, y } = geometry;
  const crossing = service.crossing_hour;
  const baseline = y(0);
  const plot = svg("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": curveSummary(service),
  });

  for (const day of [1, 8, 15, 22, 30]) {
    const tickX = x((day - 1) * 24);
    plot.append(svg("text", { x: tickX, y: height - 6, "text-anchor": day === 30 ? "end" : "start" }, `${day} sep`));
  }
  plot.append(svg("line", { x1: margin.left, x2: width - margin.right, y1: baseline, y2: baseline, stroke: "#323234" }));

  plot.append(svg("path", { d: areaPath(geometry, () => 0, (v) => Math.min(v, consumption), hour), fill: "#005866" }));
  if (crossing !== null && hour >= crossing) {
    plot.append(svg("path", { d: areaPath(geometry, () => consumption, (v) => Math.max(v, consumption), hour), fill: "#9ecc14" }));
  }

  const line = (end, start = 0) => {
    const points = [];
    for (let i = start; i <= end; i += 1) points.push(`${x(i).toFixed(1)},${y(values[i]).toFixed(1)}`);
    return points.join(" ");
  };
  plot.append(svg("polyline", { points: line(values.length - 1, hour), fill: "none", stroke: "#9ecc14", "stroke-opacity": 0.35, "stroke-width": 2 }));
  plot.append(svg("polyline", { points: line(hour), fill: "none", stroke: "#9ecc14", "stroke-width": 2 }));

  const thresholdY = y(consumption);
  const creditX = x(Math.min(hour, 719) * 0.72);
  if (y(Math.min(values[hour], consumption)) < baseline - 34) {
    plot.append(svg("text", { x: creditX, y: baseline - 14, "text-anchor": "end", class: "label-strong" }, "EE1: inyección que compensa consumo"));
  }
  if (width >= 640 && crossing !== null && hour > crossing + 24 && y(values[hour]) < thresholdY - 28) {
    const excessLabel = svg("text", { x: x(hour) - 10, y: thresholdY - 8, "text-anchor": "end", class: "label-strong" }, "EE2: excedente");
    excessLabel.style.fill = "#000";
    plot.append(excessLabel);
  }
  if (offScale) {
    const times = Math.round(consumption / injection);
    const note = width < 640
      ? `Consumo: ${times} veces la inyección, fuera de escala`
      : `Consumo del mes: ${kwh.format(consumption)} kWh. Es ${times} veces la inyección y queda fuera de esta escala.`;
    plot.append(svg("text", { x: margin.left, y: 16, class: "label-strong" }, note));
    plot.append(svg("text", { x: width - margin.right, y: y(injection) - 12, "text-anchor": "end", class: "label-strong" }, `${kwh.format(injection)} kWh inyectados en el mes`));
  } else {
    plot.append(svg("line", { x1: margin.left, x2: width - margin.right, y1: thresholdY, y2: thresholdY, stroke: "#fff", "stroke-dasharray": "6 5" }));
    plot.append(svg("text", { x: margin.left, y: thresholdY - 8, class: "label-strong" }, `Consumo del mes: ${kwh.format(consumption)} kWh`));
  }

  if (crossing !== null) {
    const crossX = x(crossing);
    plot.append(svg("circle", { cx: crossX, cy: thresholdY, r: 5, fill: "#fff", stroke: "#000", "stroke-width": 2 }));
    const anchor = crossX > width * 0.75 ? "end" : "middle";
    plot.append(svg("text", { x: crossX, y: thresholdY - 26, "text-anchor": anchor, class: "label-strong" }, `Cruce: ${formatHour(hourTimestamp(service, crossing))}`));
  }

  const cursorX = x(hour);
  plot.append(svg("line", { x1: cursorX, x2: cursorX, y1: margin.top - 8, y2: baseline, stroke: "#fff", "stroke-opacity": 0.5 }));
  plot.append(svg("circle", { cx: cursorX, cy: y(values[hour]), r: 5, fill: "#9ecc14", stroke: "#000", "stroke-width": 2 }));

  curveNode.replaceChildren(plot);
}

function curveSummary(service) {
  const { consumption_kwh: consumption, injection_kwh: injection } = service.invoice;
  const crossing = service.crossing_hour;
  const outcome = crossing === null
    ? "La inyección nunca alcanza el consumo."
    : `La inyección alcanza el consumo el ${formatHour(hourTimestamp(service, crossing))}.`;
  return `Inyección acumulada del servicio en septiembre de 2023: ${kwh.format(injection)} kWh frente a ${kwh.format(consumption)} kWh de consumo. ${outcome}`;
}

function renderReading() {
  const { service, hour } = hero;
  const accumulated = service.accumulated_kwh[hour];
  const consumption = service.invoice.consumption_kwh;
  const when = formatHour(hourTimestamp(service, hour));
  const credit = Math.min(accumulated, consumption);
  const excess = Math.max(accumulated - consumption, 0);
  const crossing = service.crossing_hour;

  let message;
  if (crossing !== null && hour >= crossing) {
    message = `Ya inyectó todo lo que consumió en el mes. EE1 queda en ${kwh.format(credit)} kWh y cada kWh adicional es excedente: EE2 suma ${kwh.format(excess)} kWh, pagados al precio de bolsa de cada hora.`;
  } else if (crossing === null && hour === service.accumulated_kwh.length - 1) {
    message = `El mes termina sin cruce: toda la inyección, ${kwh.format(accumulated)} kWh, compensa consumo como EE1, y EE2 queda en 0.`;
  } else {
    message = `Cada kWh inyectado compensa uno consumido: EE1 suma ${kwh.format(credit)} kWh. Aún no hay excedente para EE2.`;
  }
  reading.replaceChildren(el("strong", {}, `${when}. `), message);
  renderDigits(accumulated);
  scrub.setAttribute("aria-valuetext", `${when}: ${kwh.format(accumulated)} kWh inyectados`);
}

function setHour(hour) {
  hero.hour = hour;
  scrub.value = hour;
  renderCurve();
  renderReading();
}

function playMonth(duration) {
  cancelAnimationFrame(hero.animation);
  const last = hero.service.accumulated_kwh.length - 1;
  if (reduceMotion) return setHour(last);
  const start = performance.now();
  const step = (now) => {
    // El primer cuadro puede traer una marca de tiempo anterior a start.
    const progress = Math.min(Math.max((now - start) / duration, 0), 1);
    setHour(Math.round(progress * last));
    if (progress < 1) hero.animation = requestAnimationFrame(step);
  };
  hero.animation = requestAnimationFrame(step);
}

function userSetHour(hour) {
  cancelAnimationFrame(hero.animation);
  setHour(hour);
}

function selectService(sample, id, duration) {
  hero.id = id;
  hero.service = sample.services[id];
  for (const button of document.querySelectorAll(".service-option")) {
    button.setAttribute("aria-pressed", String(button.dataset.id === id));
  }
  renderConcepts(hero.service, id);
  playMonth(duration);
}

function initHero(sample) {
  const switcher = document.getElementById("service-switch");
  for (const [id] of Object.entries(sample.services)) {
    const button = el("button", { type: "button", class: "service-option", "data-id": id, "aria-pressed": "false" }, id);
    button.addEventListener("click", () => selectService(sample, id, 1400));
    switcher.append(button);
  }
  scrub.addEventListener("input", () => userSetHour(Number(scrub.value)));
  curveNode.addEventListener("pointermove", (event) => {
    const box = curveNode.getBoundingClientRect();
    const fraction = Math.min(Math.max((event.clientX - box.left - 12) / (box.width - 24), 0), 1);
    userSetHour(Math.round(fraction * 719));
  });
  curveNode.addEventListener("pointerleave", () => userSetHour(719));
  new ResizeObserver(renderCurve).observe(curveNode);
  selectService(sample, "2256", 2600);
}

function renderConcepts(service, id) {
  const { invoice } = service;
  document.getElementById("concept-service").textContent = id;
  document.getElementById("concept-rows").replaceChildren(
    ...invoice.concepts.map((line) => {
      const meta = CONCEPTS[line.concept];
      return el("tr", {},
        el("td", {}, conceptTag(line.concept), el("br"), meta.name),
        el("td", {}, meta.formula),
        el("td", { class: "num" }, kwh.format(line.quantity_kwh)),
        el("td", { class: "num" }, rate.format(line.rate)),
        el("td", { class: "num" }, amount.format(line.amount)));
    }),
  );
  document.getElementById("concept-total").replaceChildren(
    el("tr", {},
      el("th", { scope: "row", colspan: "4" }, invoice.total < 0 ? "Total: saldo a favor del usuario" : "Total a pagar"),
      el("td", { class: "num" }, amount.format(invoice.total))),
  );
  const ee2 = invoice.concepts.find((line) => line.concept === "EE2");
  document.getElementById("concept-note").textContent = ee2.quantity_kwh > 0
    ? `La tarifa de EE2 es el promedio ponderado de ${kwh.format(ee2.quantity_kwh)} kWh repartidos entre las horas posteriores al cruce. El valor real se calcula hora a hora.`
    : "Este servicio consume mucho más de lo que inyecta, así que nunca hay excedente y EE2 vale 0.";
}

function conceptTag(concept) {
  return el("span", { class: `concept-tag ${CONCEPTS[concept].kind}` }, el("i"), concept);
}

/* Diagrama entidad-relación */

const ER = {
  width: 1100,
  height: 500,
  header: 34,
  row: 26,
  tableWidth: 270,
  tables: [
    { name: "services", x: 30, y: 30, columns: [["PK", "id_service", "INTEGER"], ["", "id_market", "INTEGER"], ["", "cdi", "INTEGER NULL"], ["", "voltage_level", "SMALLINT"]] },
    { name: "records", x: 415, y: 30, columns: [["PK", "id_record", "INTEGER"], ["FK", "id_service", "INTEGER"], ["FK", "record_timestamp", "TIMESTAMP"]] },
    { name: "xm_data_hourly_per_agent", x: 800, y: 30, columns: [["PK", "record_timestamp", "TIMESTAMP"], ["", "value", "NUMERIC(16,10)"]] },
    { name: "tariffs", x: 30, y: 300, columns: [["PK", "id_tariff", "INTEGER"], ["", "id_market", "INTEGER"], ["", "voltage_level", "SMALLINT"], ["", "cdi", "INTEGER NULL"], ["", "g, t, d, r, c, p, cu", "NUMERIC(14,8)"]] },
    { name: "consumption", x: 415, y: 262, fill: "#00b7d3", ink: "#000", columns: [["PK FK", "id_record", "INTEGER"], ["", "value", "NUMERIC(14,6)"]] },
    { name: "injection", x: 800, y: 262, fill: "#9ecc14", ink: "#000", columns: [["PK FK", "id_record", "INTEGER"], ["", "value", "NUMERIC(14,6)"]] },
  ],
};

function erTable(table) {
  const { header, row, tableWidth } = ER;
  const group = svg("g", { "aria-label": `Tabla ${table.name}` });
  const height = header + row * table.columns.length;
  group.append(svg("rect", { x: table.x, y: table.y, width: tableWidth, height, fill: "#141414", stroke: "#a2a2a2", "stroke-width": 1 }));
  group.append(svg("rect", { x: table.x, y: table.y, width: tableWidth, height: header, fill: table.fill ?? "#262626" }));
  const title = svg("text", { x: table.x + 12, y: table.y + 22, class: "er-title" }, table.name);
  title.style.fill = table.ink ?? "#fff";
  group.append(title);
  table.columns.forEach(([key, name, type], index) => {
    const top = table.y + header + index * row;
    if (index > 0) group.append(svg("line", { x1: table.x, x2: table.x + tableWidth, y1: top, y2: top, stroke: "#323234" }));
    group.append(svg("text", { x: table.x + 10, y: top + 18, class: "er-key" }, key));
    group.append(svg("text", { x: table.x + 58, y: top + 18 }, name));
    group.append(svg("text", { x: table.x + tableWidth - 10, y: top + 18, "text-anchor": "end", class: "er-type" }, type));
  });
  return group;
}

// Marca de cardinalidad en un extremo: (x, y) toca la tabla y (dx, dy) apunta hacia la línea.
function erEnd(x, y, dx, dy, kind) {
  const group = svg("g", { fill: "none", stroke: "#a2a2a2", "stroke-width": 1.5 });
  const px = -dy;
  const py = dx;
  const tick = (distance) => svg("line", {
    x1: x + dx * distance + px * 7, y1: y + dy * distance + py * 7,
    x2: x + dx * distance - px * 7, y2: y + dy * distance - py * 7,
  });
  if (kind === "one") group.append(tick(7), tick(13));
  if (kind === "zero-one") {
    group.append(tick(7), svg("circle", { cx: x + dx * 18, cy: y + dy * 18, r: 5, fill: "#000" }));
  }
  if (kind === "zero-many") {
    for (const side of [1, -1]) {
      group.append(svg("line", { x1: x + px * 8 * side, y1: y + py * 8 * side, x2: x + dx * 13, y2: y + dy * 13 }));
    }
    group.append(svg("circle", { cx: x + dx * 18, cy: y + dy * 18, r: 5, fill: "#000" }));
  }
  return group;
}

function erRelation(points, ends, labels, dashed = false) {
  const group = svg("g");
  group.append(svg("polyline", {
    points: points.map((point) => point.join(",")).join(" "),
    fill: "none", stroke: "#a2a2a2", "stroke-width": 1.5, ...(dashed ? { "stroke-dasharray": "6 5" } : {}),
  }));
  group.append(...ends);
  for (const [x, y, text] of labels) group.append(svg("text", { x, y, class: "er-card" }, text));
  return group;
}

function renderDiagram() {
  const diagram = svg("svg", {
    viewBox: `0 0 ${ER.width} ${ER.height}`,
    role: "img",
    "aria-label": "Diagrama entidad-relación. services tiene cero o muchos records. xm_data_hourly_per_agent tiene cero o muchos records. Cada record tiene cero o una fila en consumption y cero o una en injection. services se relaciona con tariffs mediante la vista service_tariffs, sin llave foránea.",
  });

  diagram.append(
    erRelation([[300, 100], [415, 100]], [erEnd(300, 100, 1, 0, "one"), erEnd(415, 100, -1, 0, "zero-many")], [[320, 90, "1"], [376, 90, "0..N"]]),
    erRelation([[800, 100], [685, 100]], [erEnd(800, 100, -1, 0, "one"), erEnd(685, 100, 1, 0, "zero-many")], [[772, 90, "1"], [695, 90, "0..N"]]),
    erRelation([[550, 142], [550, 262]], [erEnd(550, 142, 0, 1, "one"), erEnd(550, 262, 0, -1, "zero-one")], [[560, 164, "1"], [560, 238, "0..1"]]),
    erRelation([[640, 142], [640, 205], [935, 205], [935, 262]], [erEnd(640, 142, 0, 1, "one"), erEnd(935, 262, 0, -1, "zero-one")], [[650, 164, "1"], [945, 238, "0..1"]]),
    erRelation([[165, 168], [165, 300]], [], [], true),
  );
  diagram.append(svg("text", { x: 178, y: 224, class: "er-card" }, "Vista service_tariffs"));
  diagram.append(svg("text", { x: 178, y: 242, class: "er-muted" }, "Sin FK: mismo mercado y nivel,"));
  diagram.append(svg("text", { x: 178, y: 258, class: "er-muted" }, "y cdi solo en el nivel 1"));
  diagram.append(...ER.tables.map(erTable));

  const legendX = 415;
  const legendY = 396;
  diagram.append(
    svg("line", { x1: legendX, x2: legendX + 44, y1: legendY, y2: legendY, stroke: "#a2a2a2", "stroke-width": 1.5 }),
    svg("text", { x: legendX + 56, y: legendY + 4 }, "Llave foránea declarada en el esquema"),
    svg("line", { x1: legendX, x2: legendX + 44, y1: legendY + 26, y2: legendY + 26, stroke: "#a2a2a2", "stroke-width": 1.5, "stroke-dasharray": "6 5" }),
    svg("text", { x: legendX + 56, y: legendY + 30 }, "Relación lógica, resuelta en una vista"),
    svg("text", { x: legendX, y: legendY + 60, class: "er-muted" }, "PK: llave primaria. FK: llave foránea. Las columnas son NOT NULL salvo las marcadas NULL."),
  );
  document.getElementById("er").append(diagram);
}

/* Consola de endpoints */

const SERVICE_FIELD = { name: "service_id", label: "service_id", hint: "Entero positivo, obligatorio. Servicios con datos: 2256, 2478 y 3222.", value: "2256", inputmode: "numeric" };
const MONTH_FIELD = { name: "month", label: "month", hint: "YYYY-MM, obligatorio. Los datos cubren 2023-09.", value: "2023-09" };
const OPTIONAL_MONTH_FIELD = { name: "month", label: "month", location: "query", hint: "YYYY-MM, opcional. Vacío usa todos los datos.", value: "2023-09" };

const ENDPOINTS = [
  {
    id: "invoice", method: "POST", path: "/calculate-invoice",
    summary: "Genera la factura de un servicio para un mes.",
    action: "Generar factura",
    fields: [{ ...SERVICE_FIELD, location: "body" }, { ...MONTH_FIELD, location: "body" }],
    presets: [
      ["Saldo a favor", { service_id: "2256", month: "2023-09" }],
      ["Total a pagar", { service_id: "3222", month: "2023-09" }],
      ["Servicio inexistente", { service_id: "1", month: "2023-09" }],
      ["Mes inválido", { service_id: "2256", month: "2023-13" }],
    ],
  },
  {
    id: "concept", method: "POST", path: "/calculate-concept/{concept}",
    summary: "Calcula un solo concepto de la factura.",
    action: "Calcular concepto",
    fields: [
      { name: "concept", label: "concept", location: "path", hint: "Obligatorio, en la ruta.", value: "ee2", options: ["ea", "ec", "ee1", "ee2"] },
      { ...SERVICE_FIELD, location: "body" },
      { ...MONTH_FIELD, location: "body" },
    ],
    presets: [
      ["EE2 de 2256", { concept: "ee2", service_id: "2256", month: "2023-09" }],
      ["EE2 de 3222", { concept: "ee2", service_id: "3222", month: "2023-09" }],
      ["Mes sin datos", { concept: "ea", service_id: "2256", month: "2024-01" }],
    ],
  },
  {
    id: "statistics", method: "GET", path: "/client-statistics/{service_id}",
    summary: "Consulta totales, promedios y máximos de consumo e inyección de un servicio.",
    action: "Consultar estadísticas",
    fields: [{ ...SERVICE_FIELD, location: "path", hint: "Entero, obligatorio, en la ruta. Servicios con datos: 2256, 2478 y 3222." }, OPTIONAL_MONTH_FIELD],
    presets: [
      ["Septiembre de 2023", { service_id: "2256", month: "2023-09" }],
      ["Todos los datos", { service_id: "2478", month: "" }],
      ["Servicio inexistente", { service_id: "1", month: "2023-09" }],
    ],
  },
  {
    id: "load", method: "GET", path: "/system-load",
    summary: "Consulta la carga por hora: el consumo sumado de todos los servicios.",
    action: "Consultar carga",
    fields: [
      OPTIONAL_MONTH_FIELD,
      { name: "limit", label: "limit", location: "query", hint: "Horas por página, de 1 a 5000. Por defecto 1000.", value: "720", inputmode: "numeric" },
      { name: "offset", label: "offset", location: "query", hint: "Horas a omitir, desde 0. Por defecto 0.", value: "0", inputmode: "numeric" },
    ],
    presets: [
      ["Mes completo", { month: "2023-09", limit: "720", offset: "0" }],
      ["Primer día", { month: "2023-09", limit: "24", offset: "0" }],
      ["limit fuera de rango", { month: "2023-09", limit: "6000", offset: "0" }],
    ],
  },
];

const ERROR_ADVICE = {
  SERVICE_NOT_FOUND: "Usa uno de los servicios de muestra: 2256, 2478 o 3222.",
  NO_DATA_FOR_PERIOD: "Los datos de muestra cubren 2023-09.",
  VALIDATION_ERROR: "Corrige los campos indicados y envía de nuevo.",
  DATABASE_UNAVAILABLE: "Comprueba que el contenedor de la base de datos esté activo con docker compose ps.",
};

const form = document.getElementById("endpoint-form");
const resultBody = document.getElementById("result-body");
const rawJson = document.getElementById("raw-json");
let current = ENDPOINTS[0];

function fieldValues() {
  return Object.fromEntries(current.fields.map((field) => [field.name, form.elements[field.name].value.trim()]));
}

function buildRequest() {
  const values = fieldValues();
  const body = {};
  const query = new URLSearchParams();
  let path = current.path;
  for (const field of current.fields) {
    const value = values[field.name];
    if (field.location === "path") path = path.replace(`{${field.name}}`, encodeURIComponent(value));
    if (!value) continue;
    if (field.location === "query") query.set(field.name, value);
    if (field.location === "body") body[field.name] = field.name === "service_id" && /^-?\d+$/.test(value) ? Number(value) : value;
  }
  const search = query.size ? `?${query}` : "";
  return { url: `${path}${search}`, body: current.method === "POST" ? JSON.stringify(body) : null };
}

function shellQuote(value) {
  return `'${value.replaceAll("'", `'\\''`)}'`;
}

function updateCurl() {
  const { url, body } = buildRequest();
  const target = shellQuote(`${window.location.origin}${url}`);
  document.getElementById("curl-code").textContent = body
    ? `curl -X POST ${target} \\\n  -H 'Content-Type: application/json' \\\n  -d ${shellQuote(body)}`
    : `curl ${target}`;
}

function selectEndpoint(endpoint) {
  current = endpoint;
  for (const tab of document.querySelectorAll(".endpoint-tab")) {
    tab.setAttribute("aria-pressed", String(tab.dataset.id === endpoint.id));
  }
  document.getElementById("endpoint-summary").textContent = endpoint.summary;
  document.getElementById("endpoint-submit").textContent = endpoint.action;
  document.getElementById("endpoint-fields").replaceChildren(...endpoint.fields.map(renderField));
  document.getElementById("endpoint-presets").replaceChildren(...endpoint.presets.map(([label, values]) => {
    const button = el("button", { type: "button", class: "preset" }, label);
    button.addEventListener("click", () => {
      for (const [name, value] of Object.entries(values)) form.elements[name].value = value;
      submit();
    });
    return button;
  }));
  resultBody.replaceChildren(el("p", { class: "empty" }, endpoint.id === "invoice"
    ? "Escribe un servicio y un mes para generar su factura."
    : "Completa los parámetros y envía la solicitud para ver el resultado."));
  rawJson.hidden = true;
  updateCurl();
}

function renderField(field) {
  const id = `field-${field.name}`;
  const label = el("label", { for: id }, el("code", {}, field.label));
  const input = field.options
    ? el("select", { id, name: field.name }, ...field.options.map((option) => el("option", { value: option }, option)))
    : el("input", { id, name: field.name, type: "text", autocomplete: "off", spellcheck: "false", ...(field.inputmode ? { inputmode: field.inputmode } : {}) });
  input.value = field.value;
  return el("div", { class: "field" }, label, input, el("small", {}, field.hint));
}

async function submit() {
  const button = document.getElementById("endpoint-submit");
  const missing = current.fields.find((field) => field.location === "path" && !form.elements[field.name].value.trim());
  updateCurl();
  if (missing) {
    resultBody.replaceChildren(errorPanel({ code: "Falta un dato", detail: `Escribe ${missing.name}: va en la ruta de la solicitud.` }));
    rawJson.hidden = true;
    return;
  }
  const { url, body } = buildRequest();
  button.disabled = true;
  const started = performance.now();
  try {
    const response = await fetch(url, {
      method: current.method,
      ...(body ? { body, headers: { "Content-Type": "application/json" } } : {}),
    });
    const data = await response.json();
    const elapsed = Math.round(performance.now() - started);
    showResponse(response.status, elapsed, data);
  } catch {
    resultBody.replaceChildren(errorPanel({
      code: "Sin respuesta",
      detail: "La API no respondió.",
      advice: "Comprueba que esté activa con docker compose ps.",
    }));
    rawJson.hidden = true;
  } finally {
    button.disabled = false;
  }
}

function showResponse(status, elapsed, data) {
  const ok = status >= 200 && status < 300;
  const statusLine = el("p", { class: "status" }, el("span", {}, "Estado ", el("strong", {}, String(status))), el("span", {}, `${elapsed} ms`));
  const renderers = { invoice: invoiceDocument, concept: conceptPanel, statistics: statisticsPanel, load: loadPanel };
  const content = ok ? renderers[current.id](data) : errorPanel({ ...data, advice: ERROR_ADVICE[data.code] });
  resultBody.replaceChildren(statusLine, content);
  document.getElementById("raw-json-code").textContent = JSON.stringify(data, null, 2);
  rawJson.hidden = false;
  if (current.id === "load" && ok) drawLoad(data);
}

function errorPanel({ code, detail, errors, advice }) {
  const panel = el("div", { class: "panel panel-error" }, el("h3", {}, code), el("p", {}, detail));
  if (errors?.length) {
    panel.append(el("ul", {}, ...errors.map((item) => el("li", {}, el("code", {}, item.field), `: ${item.message}`))));
  }
  if (advice) panel.append(el("p", {}, advice));
  return panel;
}

// La factura: resultado final del proceso. Solo muestra datos que devuelve la API.
function invoiceDocument(invoice) {
  const inFavor = invoice.total < 0;
  const rows = invoice.concepts.map((line) => el("tr", {},
    el("td", {}, conceptTag(line.concept), el("br"), CONCEPTS[line.concept].name),
    el("td", { class: "num", "data-label": "kWh" }, kwh.format(line.quantity_kwh)),
    el("td", { class: "num", "data-label": "Tarifa" }, rate.format(line.rate)),
    el("td", { class: "num", "data-label": "Valor" }, money.format(line.amount))));
  const print = el("button", { type: "button", class: "print" }, "Imprimir o guardar en PDF");
  print.addEventListener("click", () => window.print());

  const head = el("thead", {}, el("tr", {},
    el("th", { scope: "col" }, "Concepto"),
    el("th", { scope: "col", class: "num" }, "kWh"),
    el("th", { scope: "col", class: "num" }, "Tarifa ($/kWh)"),
    el("th", { scope: "col", class: "num" }, "Valor")));

  return el("article", { class: "invoice", "aria-label": "Factura generada" },
    el("div", { class: "invoice-head" },
      el("h3", {}, "Factura de energía"),
      el("p", {}, monthName(invoice.month))),
    el("dl", { class: "invoice-meta" },
      el("div", {}, el("dt", {}, "Servicio"), el("dd", {}, String(invoice.service_id))),
      el("div", {}, el("dt", {}, "Consumo"), el("dd", {}, `${kwh.format(invoice.consumption_kwh)} kWh`)),
      el("div", {}, el("dt", {}, "Inyección"), el("dd", {}, `${kwh.format(invoice.injection_kwh)} kWh`))),
    el("div", { class: "table-scroll invoice-table" },
      el("table", { class: "data" }, head, el("tbody", {}, ...rows))),
    el("div", { class: "invoice-total" },
      el("span", {}, inFavor ? "Saldo a favor del usuario" : "Total a pagar"),
      el("strong", {}, money.format(Math.abs(invoice.total)))),
    el("p", { class: "invoice-foot" }, "El total se calcula con precisión completa y se redondea una sola vez. Puede diferir en $0,01 de la suma de las líneas."),
    el("div", { class: "invoice-actions" }, print));
}

function conceptPanel(line) {
  return el("div", { class: "panel" },
    el("h3", {}, `${line.concept}: ${CONCEPTS[line.concept].name}`),
    el("p", {}, `Servicio ${line.service_id}, ${monthName(line.month)}. Fórmula: ${CONCEPTS[line.concept].formula}.`),
    el("div", { class: "stat-grid" }, el("dl", {},
      el("dt", {}, "Cantidad"), el("dd", {}, `${kwh.format(line.quantity_kwh)} kWh`),
      el("dt", {}, "Tarifa"), el("dd", {}, `${rate.format(line.rate)} $/kWh`),
      el("dt", {}, "Valor"), el("dd", {}, money.format(line.amount)))));
}

function energyBlock(title, stats) {
  return el("div", {}, el("h3", {}, title), el("dl", {},
    el("dt", {}, "Total"), el("dd", {}, `${kwh.format(stats.total_kwh)} kWh`),
    el("dt", {}, "Promedio por hora"), el("dd", {}, `${kwh.format(stats.average_kwh)} kWh`),
    el("dt", {}, "Máximo"), el("dd", {}, `${kwh.format(stats.max_kwh)} kWh`),
    el("dt", {}, "Hora del máximo"), el("dd", {}, stats.peak_at ? formatHour(stats.peak_at) : "Sin valores")));
}

function statisticsPanel(stats) {
  return el("div", { class: "panel" },
    el("p", {}, `Servicio ${stats.service_id}, ${stats.month ? monthName(stats.month) : "todos los datos"}, ${stats.hours} horas.`),
    el("div", { class: "stat-grid" }, energyBlock("Consumo", stats.consumption), energyBlock("Inyección", stats.injection)),
    el("p", {}, el("strong", {}, `Balance neto: ${kwh.format(stats.net_balance_kwh)} kWh. `), "Es consumo menos inyección: si es negativo, inyectó más de lo que consumió."));
}

function loadPanel(load) {
  return el("div", { class: "panel" },
    el("p", {}, `${load.total_hours} horas en el periodo, promedio de ${kwh.format(load.average_load_kwh)} kWh.`),
    el("p", {}, el("strong", {}, `Hora pico: ${formatHour(load.peak.timestamp)}, ${kwh.format(load.peak.load_kwh)} kWh.`)),
    load.items.length
      ? el("div", { id: "load-chart" })
      : el("p", {}, "Esta página no tiene horas: reduce offset."),
    el("p", { class: "load-readout", id: "load-readout" }, load.items.length ? `Página: ${load.items.length} horas desde ${formatHour(load.items[0].timestamp)}.` : ""));
}

function drawLoad(load) {
  const holder = document.getElementById("load-chart");
  if (!holder) return;
  const width = holder.clientWidth || 600;
  const height = 176;
  const top = Math.max(...load.items.map((item) => item.load_kwh)) * 1.08 || 1;
  const x = (index) => (load.items.length === 1 ? width / 2 : (index / (load.items.length - 1)) * width);
  const y = (value) => height - 2 - (value / top) * (height - 8);
  const chart = svg("svg", {
    class: "load-chart",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `Carga por hora de ${load.items.length} horas. La página incluye valores hasta ${kwh.format(top / 1.08)} kWh.`,
  });
  chart.append(svg("line", { x1: 0, x2: width, y1: height - 2, y2: height - 2, stroke: "#323234" }));
  chart.append(svg("polyline", {
    points: load.items.map((item, index) => `${x(index).toFixed(1)},${y(item.load_kwh).toFixed(1)}`).join(" "),
    fill: "none", stroke: "#00b7d3", "stroke-width": 2,
  }));
  const cursor = svg("circle", { r: 5, fill: "#00b7d3", stroke: "#fff", "stroke-width": 2, visibility: "hidden" });
  chart.append(cursor);
  chart.addEventListener("pointermove", (event) => {
    const box = chart.getBoundingClientRect();
    const index = Math.round(((event.clientX - box.left) / box.width) * (load.items.length - 1));
    const item = load.items[Math.min(Math.max(index, 0), load.items.length - 1)];
    cursor.setAttribute("cx", x(load.items.indexOf(item)));
    cursor.setAttribute("cy", y(item.load_kwh));
    cursor.setAttribute("visibility", "visible");
    document.getElementById("load-readout").textContent = `${formatHour(item.timestamp)}: ${kwh.format(item.load_kwh)} kWh, ${item.services} servicios.`;
  });
  holder.replaceChildren(chart);
}

function initConsole() {
  document.getElementById("endpoint-tabs").append(...ENDPOINTS.map((endpoint) => {
    const tab = el("button", { type: "button", class: "endpoint-tab", "data-id": endpoint.id, "aria-pressed": "false" }, `${endpoint.method} ${endpoint.path}`);
    tab.addEventListener("click", () => selectEndpoint(endpoint));
    return tab;
  }));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submit();
  });
  form.addEventListener("input", updateCurl);
  document.getElementById("copy-curl").addEventListener("click", async (event) => {
    await navigator.clipboard.writeText(document.getElementById("curl-code").textContent);
    event.target.textContent = "Curl copiado";
  });
  selectEndpoint(ENDPOINTS[0]);
}

renderDiagram();
initConsole();
try {
  const response = await fetch("/static/sample.json");
  initHero(await response.json());
} catch {
  reading.textContent = "No se pudo cargar la curva de muestra. Recarga la página.";
}
