async function calcular() {
    const distance = document.getElementById("distance").value;
    const type = document.getElementById("type").value;

    const res = await fetch('/api/quote', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({distance, type})
    });

    const data = await res.json();

    document.getElementById("resultado").innerHTML = `
        <h3>Total: €${data.total}</h3>
        <p>${data.nota}</p>
    `;
}

async function carregarSettings() {
    const res = await fetch('/api/settings');
    const data = await res.json();

    for (let key in data) {
        if (document.getElementById(key)) {
            document.getElementById(key).value = data[key];
        }
    }
}

async function guardarSettings() {
    const payload = {
        basePrice: basePrice.value,
        percentage: percentage.value,
        deslocacao_0_10: deslocacao_0_10.value,
        deslocacao_10_25: deslocacao_10_25.value,
        deslocacao_25_40: deslocacao_25_40.value,
        deslocacao_40: deslocacao_40.value
    };

    await fetch('/api/settings', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });

    alert("Configurações guardadas.");
}

async function carregarFotos() {
    const res = await fetch('/api/photos');
    const data = await res.json();

    let html = "";
    data.forEach(img => {
        html += `<img src="${img}" width="150" style="margin:5px;">`;
    });

    document.getElementById("photos").innerHTML = html;
      }
