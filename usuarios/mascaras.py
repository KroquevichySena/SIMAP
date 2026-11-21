"""
Máscaras para e-mail e RGM nas listagens.

Numa lista, a coordenação e o docente só precisam reconhecer a pessoa, não ler
o dado inteiro. Por isso as listagens mostram só o começo do e-mail e o final
do RGM. O dado completo continua no banco, na busca da lista de usuários, na
tela de confirmação de uma ação sobre a conta e no formulário de edição do
Admin, que são os lugares onde ele é necessário.

A parte escondida vira sempre "***", do mesmo tamanho, para a máscara não
revelar quantos caracteres o dado tem.
"""

OCULTO = "***"


def mascarar_email(email):
    """ana.martins@umc.br -> an***@umc.br"""
    if not email:
        return ""
    usuario, arroba, dominio = email.partition("@")
    if not arroba:
        return OCULTO
    visivel = usuario[:2] if len(usuario) > 2 else usuario[:1]
    return f"{visivel}{OCULTO}@{dominio}"


def mascarar_rgm(rgm):
    """11231102733 -> ***2733"""
    if not rgm:
        return ""
    if len(rgm) <= 4:
        return OCULTO
    return f"{OCULTO}{rgm[-4:]}"
