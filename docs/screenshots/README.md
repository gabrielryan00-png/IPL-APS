# Screenshots — IPL-APS

Salve as capturas de tela do sistema nesta pasta com os nomes abaixo.

| Arquivo | Conteúdo | Anonimização necessária |
|---|---|---|
| `painel_territorio.png` | Painel Geral do Território | Não |
| `vigilancia_analitica.png` | Tela Vigilância Analítica | Não |
| `resumo_clinico_triagem.png` | Resumo Clínico de Triagem (perfil individual sem nome) | Não |
| `lacuna_analitica.png` | Lacuna Analítica — Exames Essenciais | Não |
| `pacientes_criticos_original.png` | Lista de pacientes críticos **com nomes reais** | **Sim — rodar script** |
| `pacientes_criticos.png` | Versão anonimizada gerada pelo script | — gerado automaticamente |

## Gerar versão anonimizada

```bash
# a partir da raiz do projeto
python docs/anonimizar_print_pacientes.py
```

O script cobre os nomes com blocos opacos e insere labels "PACIENTE 1",
"PACIENTE 2" etc., preservando scores e indicadores clínicos.
`pacientes_criticos_original.png` **não** é commitado (listado no .gitignore).
