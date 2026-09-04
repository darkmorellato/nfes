from backend.database import get_nfe_detail


def generate_labels_html(chave: str, margem_lucro_pct: float = 30.0, modelo: str = "pimaco_6180") -> str:
    """Gera o layout HTML pronto para impressão de etiquetas de gôndola/produtos com código de barras."""
    doc = get_nfe_detail(chave)
    if not doc:
        return "<p>NF-e não encontrada.</p>"

    produtos = doc.get("produtos", [])
    if not produtos:
        return "<p>Nenhum produto cadastrado nesta NF-e.</p>"

    dest_nome = doc.get("destinatario_nome") or "EMPRESA"
    num_nfe = doc.get("numero") or "NF-e"

    labels_html = []
    for prod in produtos:
        desc = prod.get("descricao", "PRODUTO")
        cod = prod.get("ean") or prod.get("codigo") or chave[-8:]
        ncm = prod.get("ncm", "")
        v_custo = float(prod.get("valor_unitario") or 0.0)
        v_venda = v_custo * (1.0 + margem_lucro_pct / 100.0) if v_custo > 0 else 0.0
        qtd = int(float(prod.get("quantidade") or 1.0))
        qtd = max(1, min(qtd, 100))  # Limite seguro

        for _ in range(qtd):
            labels_html.append(f"""
                <div class="label-item">
                    <div class="label-empresa">{dest_nome[:30]}</div>
                    <div class="label-titulo">{desc[:45]}</div>
                    <div class="label-ncm">NCM: {ncm} | NF: {num_nfe}</div>
                    <div class="label-barcode">
                        <svg class="barcode-svg" data-code="{cod}"></svg>
                    </div>
                    <div class="label-preco">
                        <span class="label-rs">R$</span> {v_venda:,.2f}
                    </div>
                </div>
            """)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Etiquetas de Produtos - NF-e {num_nfe}</title>
        <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
        <style>
            @page {{
                size: A4;
                margin: 8mm;
            }}
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 10px;
                background: #f4f6f9;
            }}
            .no-print {{
                background: #1b4f72;
                color: #fff;
                padding: 12px 20px;
                border-radius: 6px;
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .btn-print {{
                background: #27ae60;
                color: #fff;
                border: none;
                padding: 8px 18px;
                border-radius: 4px;
                font-weight: bold;
                cursor: pointer;
                font-size: 14px;
            }}
            .labels-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 6mm;
                background: #fff;
                padding: 10px;
            }}
            .label-item {{
                border: 1px dashed #999;
                border-radius: 4px;
                padding: 6px;
                text-align: center;
                box-sizing: border-box;
                height: 38mm;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                background: #fff;
            }}
            .label-empresa {{
                font-size: 8px;
                color: #555;
                font-weight: bold;
                text-transform: uppercase;
                white-space: nowrap;
                overflow: hidden;
            }}
            .label-titulo {{
                font-size: 10px;
                font-weight: bold;
                color: #111;
                line-height: 1.1;
                max-height: 22px;
                overflow: hidden;
            }}
            .label-ncm {{
                font-size: 7.5px;
                color: #666;
            }}
            .label-barcode {{
                margin: 1px 0;
            }}
            .label-barcode svg {{
                max-width: 90%;
                height: 24px;
            }}
            .label-preco {{
                font-size: 13px;
                font-weight: 900;
                color: #b00020;
            }}
            .label-rs {{
                font-size: 9px;
                font-weight: normal;
            }}
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ background: #fff; padding: 0; }}
                .labels-grid {{ padding: 0; }}
                .label-item {{ border: 1px solid #ccc; }}
            }}
        </style>
    </head>
    <body>
        <div class="no-print">
            <div>
                <b>🏷️ Impressão de Etiquetas de Preço e Código de Barras</b> (NF-e {num_nfe} - {dest_nome})
                <div style="font-size:12px;opacity:0.9;">Margem aplicada: +{margem_lucro_pct:.1f}% | Total de {len(labels_html)} etiqueta(s)</div>
            </div>
            <button type="button" class="btn-print" onclick="window.print();">🖨️ Imprimir Etiquetas</button>
        </div>

        <div class="labels-grid">
            {"".join(labels_html)}
        </div>

        <script>
            window.onload = function() {{
                document.querySelectorAll(".barcode-svg").forEach(function(svg) {{
                    var code = svg.getAttribute("data-code") || "12345678";
                    try {{
                        JsBarcode(svg, code, {{
                            format: "CODE128",
                            width: 1.2,
                            height: 24,
                            displayValue: true,
                            fontSize: 9,
                            margin: 0
                        }});
                    }} catch(e) {{
                        console.warn("Erro ao gerar barcode:", e);
                    }}
                }});
            }};
        </script>
    </body>
    </html>
    """
    return html_content
