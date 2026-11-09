
const formulario = document.getElementById("formLogin");
const mensagem = document.getElementById("mensagem");

formulario.addEventListener("submit", async function (evento) {
    evento.preventDefault();

    const email = document.getElementById("email").value.trim();
    const senha = document.getElementById("senha").value;

    mensagem.textContent = "Verificando acesso...";
    mensagem.style.color = "#087f9f";

    try {
        const resposta = await fetch("/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, senha })
        });

        const dados = await resposta.json();

        if (resposta.ok) {
            mensagem.textContent = dados.mensagem;
            mensagem.style.color = "green";

            window.location.href = "/painel";
        } else {
            mensagem.textContent = dados.erro;
            mensagem.style.color = "red";
        }
    } catch (erro) {
        mensagem.textContent = "Não foi possível conectar ao servidor.";
        mensagem.style.color = "red";
    }
});
