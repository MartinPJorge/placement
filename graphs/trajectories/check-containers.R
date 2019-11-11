library("igraph")
library(ggmap)

# Valencia haven map
haven_borders <- c(bottom = 39.419224, top = 39.437913,
                   left = -0.341373, right = -0.304092)
map <- get_stamenmap(haven_borders, zoom=16, maptype = "toner-lite")
map_valencia_haven <- ggmap(map)
    
    
    
containers_graph <- read_graph('containers.gml', format='gml')
corners <- V(containers_graph)
corners_labels <- vertex_attr(containers_graph, name='label',
                              index = V(containers_graph))

# Number of container rows, for each column of containers
column_rows <- c(10, 14, 14, 14, 15, 15)
for (col in 1:length(column_rows)) {
  for (row in 1:column_rows[col]) {
    label_tl <- paste('r', row, 'c', col, 'tl', sep='')
    label_tr <- paste('r', row, 'c', col, 'tr', sep='')
    label_bl <- paste('r', row, 'c', col, 'bl', sep='')
    label_br <- paste('r', row, 'c', col, 'br', sep='')
    
    
    idx_tl <- which(corners_labels == label_tl, arr.ind = TRUE)
    idx_tr <- which(corners_labels == label_tr, arr.ind = TRUE)
    idx_bl <- which(corners_labels == label_bl, arr.ind = TRUE)
    idx_br <- which(corners_labels == label_br, arr.ind = TRUE)
    
    tl_lon <- vertex_attr(containers_graph, name='lon', index=idx_tl)
    tr_lon <- vertex_attr(containers_graph, name='lon', index=idx_tr)
    bl_lon <- vertex_attr(containers_graph, name='lon', index=idx_bl)
    br_lon <- vertex_attr(containers_graph, name='lon', index=idx_br)
    tl_lat <- vertex_attr(containers_graph, name='lat', index=idx_tl)
    tr_lat <- vertex_attr(containers_graph, name='lat', index=idx_tr)
    bl_lat <- vertex_attr(containers_graph, name='lat', index=idx_bl)
    br_lat <- vertex_attr(containers_graph, name='lat', index=idx_br)
    
    container_square <- data.frame(lon=c(tl_lon, tr_lon, br_lon, bl_lon, tl_lon),
                                   lat=c(tl_lat, tr_lat, br_lat, bl_lat, tl_lat))
    
    map_valencia_haven <- map_valencia_haven + geom_path(
                           aes(x = lon, y = lat),  colour = "blue",
                           size = 0.5, alpha = .5,
                           data = container_square, lineend = "round"
                         )
  }
}

map_valencia_haven
