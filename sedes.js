const sedesTecsup = {
  arequipa: { nombre: "Tecsup Arequipa", direccion: "Urb. Monterrey Lote D-8, José Luis Bustamante y Rivero, Arequipa" },
  lima: { nombre: "Tecsup Lima", direccion: "Av. Cascanueces 2221, Santa Anita, Lima" },
  trujillo: { nombre: "Tecsup Trujillo", direccion: "Urbanización Tecsup, Víctor Larco Herrera, Trujillo" },
};

function enlaceMaps(sede) {
  const { nombre, direccion } = sedesTecsup[sede];
  const parametros = new URLSearchParams({ api: "1", destination: `${nombre}, ${direccion}` });
  return `https://www.google.com/maps/dir/?${parametros}`;
}
