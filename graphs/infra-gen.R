library(mecgen)
library(SDMTools)

# Read the micro cells
micros <- read.csv(file="fixed-cells/cobo-calleja/micro-cells.csv", header=TRUE,
                   sep = ' ')
micros$type <- rep('micro', nrow(micros))


# Generate with random uniform the pico cells
repulsion <- 50
cobo.bl <- c(40.253541,-3.775409)
cobo.br <- c(40.253541,-3.737324)
cobo.tr <- c(40.276686,-3.737324)
cobo.tl <- c(40.276686,-3.775409)

# Insert the first pico cell
curr_pico.lon <- runif(1, min = cobo.bl[2], max = cobo.br[2])
curr_pico.lat <- runif(1, min = cobo.br[1], max = cobo.tr[1])
pico_cells <- data.frame(lon = curr_pico.lon, lat = curr_pico.lat, type='pico')

while(nrow(pico_cells) < 40 - 1) {
  curr_pico.lon <- runif(1, min = cobo.bl[2], max = cobo.br[2])
  curr_pico.lat <- runif(1, min = cobo.br[1], max = cobo.tr[1])
  
  no_overlap <- TRUE
  for (row in 1:nrow(pico_cells)) {
    pico <- pico_cells[row,]
    dis <- SDMTools::distance(lat1 = curr_pico.lat, lon1 = curr_pico.lon,
                              lat2 = pico$lat, lon2 = pico$lon)$distance
    if (dis < repulsion) {
      no_overlap <- FALSE
      break
    }
  }
  
  if (no_overlap) {
    pico_cells <- rbind(pico_cells,
                        data.frame(lon=curr_pico.lon, lat=curr_pico.lat,
                                   type='pico'))
  }
}


# Obtain the cells of Cobo Calleja
cobo_cells <- rbind(micros, data.frame(head(pico_cells, 10)))
assocs <- build5GScenario(lats = cobo_cells$lat, lons = cobo_cells$lon)

# Obtain the link and nodes frames
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



# Attach remaining pico cells to the M1 nodes where other pico cells that are
# close to them attach to
orphan_picos <- data.frame()
child_picos <- data.frame()
for (row in 1:nrow(pico_cells)) {
  pico <- pico_cells[row,]
  orphan <- length(which(m1Assoc$lon == pico$lon &
                           m1Assoc$lat == pico$lat)) == 0
  if (orphan)
    orphan_picos <- rbind(orphan_picos, data.frame(pico))
  else
    child_picos <- rbind(child_picos, data.frame(pico))
}
orphan_picos$assoc_m1 <- rep(-1, nrow(orphan_picos))

# Store the used M1 switches
used_m1s <- data.frame()
for (gr in unique(m1Assoc$group)) {
  idx <- which(m1Coords$group == gr)
  used_m1s <- rbind(used_m1s, data.frame(m1Coords[idx,]))
}
# Store how many pico cells are associated to them
used_m1s$num_picos <- rep(0, nrow(used_m1s))
for (row in 2:nrow(used_m1s)) {
  used_m1 <- used_m1s[row,]
  cells_of_m1 <- subset(m1Assoc, group == used_m1$group)
  for (row2 in 1:nrow(child_picos)) {
    child_pico <- child_picos[row2,]
    filtered <- subset(cells_of_m1, lon==child_pico$lon &
                   lat==child_pico$lat)
    if(nrow(subset(cells_of_m1, lon==child_pico$lon &
                   lat==child_pico$lat)) > 0) {
      used_m1s[row,]$num_picos = used_m1s[row,]$num_picos + 1
    }
  }
}

# Store how many more pico cells they can hold (x4 pico = x1 macro)
for(row in 1:nrow(used_m1s)) {
  used_m1s[row,]$num_picos <- used_m1s[row,]$num_picos * 4
  used_m1s[row,]$num_picos <- used_m1s[row,]$num_picos -
                              (used_m1s[row,]$num_picos / 4)
}

# Find the closest orphan for each used M1
m1 <- 1
while (length(which(orphan_picos$assoc_m1 == -1)) > 0) {
  if (used_m1s[m1,]$num_picos == 0) {
    m1 <- which(used_m1s$num_picos > 0)[1]
  }
  
  m1_switch <- used_m1s[m1,]
  
  min_dis <- Inf
  min_orphan <- -1
  for (row in 1:nrow(orphan_picos)) {
    orphan_pico <- orphan_picos[row,]
    if (orphan_pico$assoc_m1 == -1) {
      dis <- SDMTools::distance(lat1 = m1_switch$lat, lon1 = m1_switch$lon,
                                lat2 = orphan_pico$lat,
                                lon2 = orphan_pico$lon)$distance
      if (dis < min_dis) {
        min_dis <- dis
        min_orphan <- row
      }
    }
  }
  
  # do the assignment
  orphan_picos[min_orphan,]$assoc_m1 = m1_switch$group
  used_m1s[m1,]$num_picos = used_m1s[m1,]$num_picos - 1
  
  # Choose next M1 switch to assign antennas
  m1 <- (m1 + 1) %% (nrow(used_m1s) + 1)
  m1 <- ifelse(m1 == 0, yes=1, no=m1)
}

# Append the M1 switches
orphan_picos$type <- NULL
orphan_picos$group <- orphan_picos$assoc_m1 
orphan_picos$assoc_m1 <- NULL
m1Assoc <- rbind(m1Assoc, orphan_picos)
  


# Create the frames
frames <- graphFrames(m1Assoc, m1Coords, m1AccAssocs, accCentCoords,
                      m2Assocs, m2Switches, m2AggAssocs, aggCentCoords,
                      m3Assocs, m3Switches)

# Add node property for the cell type
pico_nodes <- c()
micro_nodes <- c()
cell_nodes <- subset(frames$nodes, type=='cell')
for (i in 1:nrow(cell_nodes)) {
  if (nrow(subset(pico_cells, lon == cell_nodes[i,]$lon &
                              lat == cell_nodes[i,]$lat)) > 0)
    pico_nodes <- c(pico_nodes, as.character(cell_nodes[i,]$id))
  else
    micro_nodes <- c(micro_nodes, as.character(cell_nodes[i,]$id))
}
newNodes <- addNodeProps(nodes = frames$nodes, id_ = pico_nodes,
                     properties = list(size=rep('pico', length(pico_nodes)),
                                       coverageRadius=
                                         rep(100, length(pico_nodes)),
                                       delay=rep(2.5, length(pico_nodes))))
newNodes <- addNodeProps(nodes = newNodes, id_ = micro_nodes,
                     properties = list(size=rep('micro', length(micro_nodes)),
                                       coverageRadius=
                                         rep(400, length(micro_nodes)),
                                       delay=rep(5, length(micro_nodes))))
frames$nodes <- newNodes


# Attach edge servers
attachFrames <- attachServers(nodes = frames$nodes, links = frames$links,
                              numServers = 6,
                              bandwidth = 12,
                              bandwidthUnits = "Mbps",
                              distance = 0,
                              distanceUnits = "meter",
                              switchType = "m1",
                              properties = list(cpu=2, mem=20, disk=100,
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
                              properties = list(cpu=20, mem=200, disk=1000,
                                                cost=2.48),
                              idPrefix = "cloud_server")

######### THE TWO SQUARES WHERE FOG NODES APPEAR #########
# # left square
# tl = list(lat=40.266662, lon=-3.756308)
# br = list(lat=40.262594, lon=-3.751914)
# # right square
# tl2 = list(lat=40.264600, lon=-3.751753)
# br2 = list(lat=40.260469, lon=-3.748170)
square1 <- data.frame(tl_lat=40.266662, tl_lon=-3.756308,
                      br_lat=40.262594, br_lon=-3.751914)
square2 <- data.frame(tl_lat=40.264600, tl_lon=-3.751753,
                      br_lat=40.260469, br_lon=-3.748170)
squares <- rbind(square1, square2)


######## GENERATE THE FOG NODES #######
robots_per_square <- 10
d2d_delay <- 0.2
mesh_robot_connections <- ncol(combn(rep(0,robots_per_square), 2))
from_sqs <- data.frame(matrix(0, ncol = nrow(squares),
                              nrow = mesh_robot_connections))
to_sqs <- data.frame(matrix(0, ncol = nrow(squares),
                               nrow = mesh_robot_connections))
for (i in 1:nrow(squares)) {
  tos <- c()
  froms <- c()
  square <- squares[i,]
  prefix <- paste("robot_sq", i, sep="")
  attachFrames <- attachFogNodes(nodes = attachFrames$nodes,
                                 links = attachFrames$links,
                                 latB = square$br_lat, latT = square$tl_lat,
                                 lonL = square$tl_lon, lonR = square$br_lon,
                                 numNodes = robots_per_square,
                                 properties = list(cpu = 1, mem = 1, disk=10,
                                                   cost=15.27),
                                 bandwidth = 20, bandwidthUnits = "Mpbs",
                                 idPrefix = prefix)
  
  # Remove the links of the fog nodes
  attachFrames$links <- head(attachFrames$links,
                             nrow(attachFrames$links) - robots_per_square)
  
  # Connect fog nodes among them
  last_robot_ids <- as.vector(tail(attachFrames$nodes, robots_per_square)$id)
  robot_pairs <- combn(last_robot_ids, 2)
  for (c in 1:ncol(robot_pairs)) {
    link <- tail(attachFrames$links, 1)
    link$from <- robot_pairs[1,c]
    link$to <- robot_pairs[2,c]
    
    # Include the robot link in the connectivity data.frame
    froms <- c(froms, link$from)
    tos <- c(tos, link$to)
    
    # Get robot coordinates
    from_row <- as.numeric(rownames(subset(attachFrames$nodes, id==link$from)))
    from_lon <- attachFrames$nodes[from_row,]$lon
    from_lat <- attachFrames$nodes[from_row,]$lat
    to_row <- as.numeric(rownames(subset(attachFrames$nodes, id==link$to)))
    to_lon <- attachFrames$nodes[to_row,]$lon
    to_lat <- attachFrames$nodes[to_row,]$lat
    
    # Attach the robot with its distances
    link$distance <- SDMTools::distance(lat1 = to_lat, lon1 = to_lon,
                                        lat2 = from_lat,
                                        lon2 = from_lon)$distance
    attachFrames$links <- rbind(attachFrames$links, link)
    
  }
  
  # Specify the meshed connections delays of robots inside the square
  from_sqs[,i] <- froms
  to_sqs[,i] <- tos
  
  # Attach endpoint node
  square_endpoint <- paste("endpoint_sq", i, sep="")
  last_node <- tail(attachFrames$nodes, 1)
  last_robot <- tail(attachFrames$nodes, 1)
  last_link <- tail(attachFrames$links, 1)
  #
  last_node$id <- square_endpoint
  last_node$type <- 'endpoint'
  last_node$cpu <- 0
  last_node$mem <- 0
  last_node$disk <- 0
  attachFrames$nodes <- rbind(attachFrames$nodes, last_node)
  #
  last_link$from <- square_endpoint
  last_link$to <- last_robot$id
  attachFrames$links <- rbind(attachFrames$links, last_link)
}

######### SET THE D2D DELAY BETWEEN ROBOTS #########
d2d_delay <- 0.2
for (i in 1:nrow(squares)) {
  newLinks <- addLinkProps(links = attachFrames$links, from_ = from_sqs[,i],
                           to_ = to_sqs[,i],
                           properties = list(delay=rep(d2d_delay,
                                                       nrow(from_sqs))))
  attachFrames$links <- newLinks
}



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


# Store the generated graph
links <- attachFrames$links
nodes <- attachFrames$nodes
g = igraph::graph_from_data_frame(links, vertices = nodes, directed = FALSE)
igraph::write_graph(graph = g, file = "/tmp/infra.gml", format = "gml")

