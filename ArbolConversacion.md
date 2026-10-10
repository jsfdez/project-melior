# Melior: árbol de opciones

Diseño del árbol de preguntas y respuestas de Melior, la app de comunicación asistida que se controla solo con movimientos de cabeza. El usuario recorre el árbol seleccionando opciones con la dirección de la cabeza y la frase elegida se pronuncia con ElevenLabs.

Este documento define solo la parte **estática** del árbol. A partir de ciertos nodos, Gemma genera las opciones según la hora y la conversación reciente.

## Principios de diseño

- **Máximo 4 opciones por pantalla, una por dirección de la cabeza:** arriba, abajo, izquierda y derecha. Se elige inclinando o girando la cabeza hacia esa dirección y manteniéndola ~0,8 s (ajustable por usuario); volver al centro reinicia el tiempo. No hay cursor ni puntería, así que tolera temblor y poco rango de movimiento.
- **Orden de las opciones:** en cada nodo del árbol, las 4 opciones se leen en el orden ↑ arriba, ↓ abajo, ← izquierda, → derecha. La posición es fija en cada nivel para crear memoria muscular.
- **Nivel 1 fijo:** Responder, Necesito, Urgencia y Más.
- **Atrás y Confirmar no ocupan ninguna de las 4 opciones.** Como las 4 direcciones ya eligen opciones, sacudir y asentir ya no sirven (se confundirían con elegir). Con el motor de gestos actual (`src/interaction/gesture_engine.py`): se elige apuntando con la cabeza y manteniéndola quieta ~1 s; **Atrás = parpadeo largo** (~0,6 s, el parpadeo natural no cuenta); **Confirmar** una opción crítica `[!]` = repetir la misma dirección (hay que volver al centro y apuntar de nuevo). Pendiente de probar con un usuario real.
- **Frases rápidas.** Lo más frecuente se dice en 2 o 3 selecciones. Solo Dolor y Comodidad llegan a 4 niveles, porque necesitan precisión.
- **Frases neutras en género.** Se evita "cansado/a" (se usa "Tengo sueño", "Me siento triste") para no depender de una configuración.
- **Las acciones críticas piden confirmación** (asentir) antes de hablar, para evitar falsos positivos.
- **Privacidad.** A Gemma y a ElevenLabs solo se envía el texto mínimo necesario, sin datos personales ni de salud.

## Leyenda

| Marca | Significado |
|-------|-------------|
| (sin marca) | Menú o frase que se dice en voz alta |
| `[IA]` | Gemma genera 4 opciones en este punto |
| `[!]` | Crítico: pide confirmación antes de hablar |
| `[AJ]` | Ajuste de la app, no habla |

## El árbol

```
RESPONDER
├── Sí
│   ├── Sí
│   ├── Sí, gracias
│   ├── Sí, por favor
│   └── [IA] Sí, y…
├── No
│   ├── No
│   ├── No, gracias
│   ├── Ahora no
│   └── [IA] No, porque…
├── Ni sí ni no
│   ├── No sé
│   ├── Quizás
│   ├── Más tarde
│   └── Dame un momento
└── [IA] Otra respuesta

NECESITO
├── Beber / comer
│   ├── Agua
│   ├── Café o té
│   ├── [IA] Tengo hambre
│   └── [IA] Otra cosa
├── Baño / aseo
│   ├── Baño ya
│   ├── Baño en un rato
│   ├── Lavarme
│   └── Cambiarme de ropa
├── Comodidad
│   ├── Postura
│   │   ├── Incorporarme
│   │   ├── Tumbarme
│   │   ├── Girarme
│   │   └── Ajustar almohada
│   ├── Temperatura
│   │   ├── Tengo frío
│   │   ├── Tengo calor
│   │   ├── Abrir ventana
│   │   └── Cerrar ventana
│   ├── Luz y ruido
│   │   ├── Más luz
│   │   ├── Menos luz
│   │   ├── Menos ruido
│   │   └── Cerrar la puerta
│   └── Algo me molesta
└── Mis cosas
    ├── Gafas
    ├── Móvil o tablet
    ├── Medicación
    └── [IA] Otra cosa

URGENCIA
├── [!] No puedo respirar
├── Me duele
│   ├── Cabeza            → Poco · Bastante · Muchísimo
│   ├── Pecho / barriga   → Poco · Bastante · [!] Muchísimo
│   ├── Espalda / cuello  → Poco · Bastante · Muchísimo
│   └── Brazos / piernas  → Poco · Bastante · Muchísimo
├── Me encuentro mal
│   ├── Mareo
│   ├── Náuseas
│   ├── Fiebre o escalofríos
│   └── Muy débil
└── Pedir ayuda
    ├── Llama a alguien
    ├── Ven, por favor
    ├── [!] Llama a emergencias
    └── [!] Alarma

MÁS
├── Me siento
│   ├── Bien
│   ├── Triste
│   ├── Nervioso o con miedo
│   └── Enfadado o frustrado
├── Quiero
│   ├── Compañía
│   │   ├── Quédate conmigo
│   │   ├── Quiero estar solo
│   │   ├── Llamar a mi familia
│   │   └── Que vengan a verme
│   ├── Tele
│   │   ├── Encender
│   │   ├── Apagar
│   │   ├── Subir volumen
│   │   └── Bajar volumen
│   ├── Música
│   │   ├── Tranquila
│   │   ├── Animada
│   │   ├── Parar
│   │   └── [IA] Elegir canción
│   └── Descansar / salir
│       ├── Siesta o dormir   (según la hora)
│       ├── Apagar la luz
│       ├── Tomar el aire
│       └── Cambiar de habitación
├── Hablar
│   ├── Saludos
│   │   ├── Saludo según la hora   (buenos días, tardes o noches)
│   │   ├── Hola
│   │   ├── ¿Cómo estás?
│   │   └── Adiós
│   ├── Cortesía
│   │   ├── Gracias
│   │   ├── Por favor
│   │   ├── Perdón
│   │   └── Te quiero
│   ├── Aclarar
│   │   ├── Repite
│   │   ├── Más despacio
│   │   ├── Espera
│   │   └── No quería decir eso
│   └── [IA] Conversar
└── Ajustes
    ├── [AJ] Volumen de voz
    ├── [AJ] Pausar seguimiento
    ├── [AJ] Recalibrar
    └── [AJ] Idioma
```

## Dónde entra Gemma

| Nodo | Qué genera |
|------|------------|
| Responder → Sí, y… / No, porque… | Continuaciones de la respuesta |
| Responder → Otra respuesta | 4 respuestas posibles a lo último que se dijo |
| Necesito → Tengo hambre | Comidas según la hora (desayuno, comida, merienda, cena) |
| Necesito → Otra cosa (Beber / comer, Mis cosas) | Peticiones habituales según contexto |
| Más → Quiero → Música → Elegir canción | Géneros o canciones |
| Más → Hablar → Conversar | 4 frases para mantener la conversación |

Reglas para todos los nodos de IA:

- Cada llamada a Gemma devuelve una lista JSON de **6 frases** ordenadas, de pocas palabras. La pantalla enseña las **3 mejores**; la 4.ª posición es siempre **↓ «Más opciones»**, que enseña las otras 3 al instante y, en ese momento, lanza en segundo plano una llamada nueva con 6 frases distintas (sin repetir nada de lo ya generado en esa visita al nodo). Si Gemma no está disponible, se usan las opciones de reserva del nodo (más de 3, para poder seguir pasando tandas).
- Entrada mínima: hora del día y últimas frases. Sin datos personales ni de salud mientras el endpoint sea compartido.
- Gemma **nunca habla en nombre del usuario sin una selección**.
- Si la red o el LLM fallan, el nodo muestra opciones estáticas de reserva.

## Uso de la hora

Algunas opciones solo aparecen o cambian según la hora local:

- Saludos: buenos días, buenas tardes o buenas noches.
- Descansar / salir: "Siesta o dormir" aparece por la tarde y por la noche.
- Tengo hambre: Gemma adapta las sugerencias a la comida del momento.

## Frases críticas y modo sin conexión

Las frases marcadas `[!]` piden confirmación antes de hablar. Las siguientes deben funcionar sin red ni LLM, con audio pregrabado o voz local:

- No puedo respirar
- Llama a alguien
- Llama a emergencias
- Alarma
- Dolor "Muchísimo" en pecho o barriga
- Agua, Baño ya, Sí, No, Gracias

## Decisiones abiertas

1. **Sí y No cuestan 3 selecciones** (Responder, Sí, Sí) por tener variantes. Alternativa: botones directos "Sí" y "No" en el nivel 2, con las variantes generadas por la IA.
2. **Dolor y Comodidad llegan a 4 niveles.** Decidir si se recortan o se mantienen por la precisión.
3. **Dolor en pecho o barriga:** confirmar que "Muchísimo" escala a crítico en ambas zonas, o solo en el pecho.
4. **Frases de emergencia:** validar el texto exacto y qué voz local se usa como respaldo.
5. **Validación con un usuario real o terapeuta**, sobre todo el vocabulario de Necesito y Me siento.
6. **Idiomas:** español primero. Las etiquetas y frases deberán poder traducirse al añadir el inglés.
7. **Gestos de Atrás y Confirmar:** definir el gesto definitivo (mantener el centro, parpadeo largo, boca abierta) y probarlo con un usuario real.
8. **Asignación de direcciones en el nivel 1:** con el orden ↑ ↓ ← →, la raíz queda Responder ↑, Necesito ↓, Urgencia ←, Más →. Valorar si Urgencia debe ir en otra posición.
9. **Ajustes:** definir si las acciones del sistema van aquí o en una vía separada para el cuidador.
