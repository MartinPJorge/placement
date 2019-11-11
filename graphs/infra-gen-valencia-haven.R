library(mecgen)
library(SDMTools)

# Read the micro cells
cells <- read.csv(file="valencia-haven-aaus.csv", header=TRUE, sep = ',')


# Generate with random uniform the pico cells
haven_borders <- c(bottom = 39.419224, top = 39.437913,
                   left = -0.341373, right = -0.304092)
map <- get_stamenmap(haven_borders, zoom=16, maptype = "toner-lite")
map_valencia_haven <- ggmap(map)
repulsion <- 50

vlc.bl <- c(39.419224,-0.341373)
vlc.br <- c(39.419224,-0.304092)
vlc.tr <- c(39.437913,-0.304092)
vlc.tl <- c(39.437913,-0.341373)


# Obtain the link and nodes frames
assocs <- build5GScenario(lats = cells$lat, lons = cells$lon)
m1Assoc <- assocs[[1]]
m1Coords <- assocs[[2]]
m1AccAssocs <- assocs[[3]]
accCentCoords <- assocs[[4]]
m2Assocs <- assocs[[5]]
m2Switches <- assocs[[6]]
m2AggAssocs <- assocs[[7]]
aggCentCoords <- assocs[[8]]
m3Assocs <- assocs[[9]]
m3Switches <- assocs[[10]]


# Create the frames
frames <- graphFrames(m1Assoc, m1Coords, m1AccAssocs, accCentCoords,
                      m2Assocs, m2Switches, m2AggAssocs, aggCentCoords,
                      m3Assocs, m3Switches)

# Specify LTE and NR properties
nr_nodes <- c()
lte_nodes <- c()
cell_nodes <- cells
for (i in 1:nrow(cell_nodes)) {
  if (cell_nodes[i,]$type == 'lte')
    lte_nodes <- c(lte_nodes, as.character(cell_nodes[i,]$id))
  else
    nr_nodes <- c(nr_nodes, as.character(cell_nodes[i,]$id))
}
newNodes <- addNodeProps(nodes = frames$nodes, id_ = nr_nodes,
                     properties = list(size=rep('nr', length(nr_nodes)),
                                       coverageRadius=
                                         rep(700, length(nr_nodes)),
                                       delay=rep(0.75, length(nr_nodes)),
                                       cost=rep(11, length(nr_nodes))))
newNodes <- addNodeProps(nodes = newNodes, id_ = lte_nodes,
                     properties = list(size=rep('lte', length(lte_nodes)),
                                       coverageRadius=
                                         rep(8000, length(lte_nodes)),
                                       delay=rep(5, length(lte_nodes)),
                                       cost=rep(5.5, length(nr_nodes))))
frames$nodes <- newNodes


# Attach edge servers
attachFrames <- attachServers(nodes = frames$nodes, links = frames$links,
                              numServers = 6,
                              bandwidth = 12,
                              bandwidthUnits = "Mbps",
                              distance = 0,
                              distanceUnits = "meter",
                              switchType = "m1",
                              properties = list(cpu=12, mem=20, disk=100,
                                                cost=5.83),
                              idPrefix = "edge_server")


# Attach cloud servers
attachFrames <- attachServers(nodes = frames$nodes, links = frames$links,
                              numServers = 2,
                              bandwidth = 12,
                              bandwidthUnits = "Mbps",
                              distance = 0,
                              distanceUnits = "meter",
                              switchType = "m3",
                              properties = list(cpu=200, mem=200, disk=1000,
                                                cost=2.48),
                              idPrefix = "cloud_server")




######### SET FIXED INFRA DELAYS ASSUMING FIBER #########
froms <- c()
tos <- c()
delays <- c()
for (row in 1:nrow(attachFrames$links)) {
  from_id <- as.character(attachFrames$links[row,]$from)
  to_id <- as.character(attachFrames$links[row,]$to)
  distance <- as.numeric(attachFrames$links[row,]$distance)
  
  is_src_robot <- grepl("robot", from_id)
  is_dst_robot <-  grepl("robot", to_id)
  
  if (!is_src_robot && !is_dst_robot) {
    froms <- c(froms, from_id)
    tos <- c(tos, to_id)
    delays <- c(delays, distance / 3e5) # delay is in ms, distance in M, light
  }
}
newLinks <- addLinkProps(links = attachFrames$links, from_ = froms, to_ = tos,
                         properties = list(delay=delays))
attachFrames$links <- newLinks




# Generate the fiber hops delay, which include the processing delay of switches
fiber_delays <- read.csv('fiber_delays.csv', header = FALSE)
froms <- c()
tos <- c()
delays <- c()
for (row in 1:nrow(attachFrames$links)) {
  from <- as.character(attachFrames$links[row,]$from)
  to <- as.character(attachFrames$links[row,]$to)
  
  is_src_cell <-  grepl("cell", from)
  is_src_m1 <-  grepl("m1", from)
  is_dst_m1 <-  grepl("m1", to)
  is_src_m2 <-  grepl("m2", from)
  is_dst_m2 <-  grepl("m2", to)
  is_src_m3 <-  grepl("m3", from)
  is_dst_m3 <-  grepl("m3", to)
  
  if ((is_src_cell && is_dst_m1) ||
      (is_src_m1 && is_dst_m1) ||
      (is_src_m1 && is_dst_m2) ||
      (is_src_m2 && is_dst_m2) ||
      (is_src_m2 && is_dst_m2) ||
      (is_src_m3 && is_dst_m3)) {
    
    print('in')
    
    froms <- c(froms, from)
    tos <- c(tos, to)
    rand_delay <- runif(1, min=1, max=nrow(fiber_delays))
    delays <- c(delays, fiber_delays[rand_delay, ]) # delay is in ms
  }
}
newLinks <- addLinkProps(links = attachFrames$links, from_ = froms, to_ = tos,
                         properties = list(delay=delays))
attachFrames$links <- newLinks



# Store the generated graph
links <- attachFrames$links
nodes <- attachFrames$nodes
g = igraph::graph_from_data_frame(links, vertices = nodes, directed = FALSE)
igraph::write_graph(graph = g, file = "/tmp/infra.gml", format = "gml")

