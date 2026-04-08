# REQUISITOS FUNCIONAIS

## RF01

Preciso que haja uma espécie de álbum de fotos no sistema com endpoits get, post e delete

## RF02

preciso de um scheduler automático configurável para iterar sobre as fotos e atualizar no tempo configurado (ex: a cada 1 hora)

nao pode repetir nem a imagem e nem a mensagem-submensagem anterior.

## RF03

preciso ter a opção de enviar uma foto na hora, sem passar pela adição do overlay

## RF04

preciso ter um botão de ON/OFF para o scheduler automático

## RF05

melhora do front end

## RF06

ter um "álbum" de mensagens e submensagens

## RF07

ter a opção de gerar imagens darkmode no scheduler

## RF08

manter as rotas 
/api/status:

{
  "arquivo": "2026-04-08_12-47-28.png",
  "dia": "2026-04-08",
  "disponivel": true,
  "horario": "12:47:28",
  "versao": "2026-04-08_7"
}

e /api/image: content-type: image/png

retornando exatamente a mesma coisa 
