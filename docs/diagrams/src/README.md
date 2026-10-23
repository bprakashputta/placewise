# Diagram sources (D2)

Diagrams are written in [D2](https://d2lang.com) and rendered to SVG in Docker (nothing installed on the host):

```
docker run --rm -u $(id -u):$(id -g) -v "$PWD/docs/diagrams":/home/debian/src -w /home/debian/src \
  terrastruct/d2:v0.7.1 --layout elk src/<name>.d2 <name>.svg
```

Color key: blue = Placewise services, green = data or plain code steps, orange = external AI / LLM steps,
red = needs attention, dashed gray = planned or asynchronous.
