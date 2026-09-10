/**
 * Draw Road Network
 */
id = Math.random().toString(36).substring(2, 15);

BACKGROUND_COLOR = 0x0b0f19;
LANE_COLOR = 0x1e293b;
LANE_BORDER_WIDTH = 1.5;
LANE_BORDER_COLOR = 0x334155;
LANE_INNER_COLOR = 0x475569;
LANE_DASH = 10;
LANE_GAP = 12;
TRAFFIC_LIGHT_WIDTH = 4;
MAX_TRAFFIC_LIGHT_NUM = 10000;
ROTATE = 90;

CAR_LENGTH = 5;
CAR_WIDTH = 2;
CAR_COLOR = 0x38bdf8;

CAR_COLORS = [
    0x38bdf8, // Electric Cyan
    0x34d399, // Neon Emerald
    0xfbbf24, // Amber Glow
    0xa78bfa, // Cyber Violet
    0xf43f5e  // Vivid Rose
];
CAR_COLORS_NUM = CAR_COLORS.length;

NUM_CAR_POOL = 10000;

LIGHT_RED = 0xef4444;
LIGHT_GREEN = 0x10b981;

TURN_SIGNAL_COLOR = 0xFFFFFF;
TURN_SIGNAL_WIDTH = 1;
TURN_SIGNAL_LENGTH = 5;

var simulation, roadnet, steps;
var nodes = {};
var edges = {};
var logs;
var gettingLog = false;

let Application = PIXI.Application,
    Sprite = PIXI.Sprite,
    Graphics = PIXI.Graphics,
    Container = PIXI.Container,
    ParticleContainer = PIXI.particles.ParticleContainer,
    Texture = PIXI.Texture,
    Rectangle = PIXI.Rectangle
    ;

var controls = new function () {
    this.replaySpeedMax = 1;
    this.replaySpeedMin = 0.01;
    this.replaySpeed = 0.5;
    this.paused = false;
};

var trafficLightsG = {};

var app, viewport, renderer, simulatorContainer, carContainer, trafficLightContainer;
var turnSignalContainer;
var carPool;

var cnt = 0;
var frameElapsed = 0;
var totalStep;

var nodeCarNum = document.getElementById("car-num");
var nodeProgressPercentage = document.getElementById("progress-percentage");
var nodeTotalStep = document.getElementById("total-step-num");
var nodeCurrentStep = document.getElementById("current-step-num");
var nodeSelectedEntity = document.getElementById("selected-entity");

var SPEED = 3, SCALE_SPEED = 1.01;
var LEFT = 37, UP = 38, RIGHT = 39, DOWN = 40;
var MINUS = 189, EQUAL = 187, P = 80;
var LEFT_BRACKET = 219, RIGHT_BRACKET = 221;
var ONE = 49, TWO = 50;
var SPACE = 32;

var keyDown = new Set();

var turnSignalTextures = [];

let pauseButton = document.getElementById("pause");
let nodeCanvas = document.getElementById("simulator-canvas");
let replayControlDom = document.getElementById("replay-control");
let replaySpeedDom = document.getElementById("replay-speed");

let loading = false;
let infoDOM = document.getElementById("info");
let selectedDOM = document.getElementById("selected-entity");

function infoAppend(msg) {
    infoDOM.innerText += "- " + msg + "\n";
}

function infoReset() {
    infoDOM.innerText = "";
}

/**
 * Upload files
 */
let ready = false;

let roadnetData = [];
let replayData = [];
let chartData = [];

function handleChooseFile(v, label_dom) {
    return function (evt) {
        let file = evt.target.files[0];
        label_dom.innerText = file.name;
    }
}

function uploadFile(v, file, callback) {
    let reader = new FileReader();
    reader.onloadstart = function () {
        infoAppend("Loading " + file.name);
    };
    reader.onerror = function () {
        infoAppend("Loading " + file.name + "failed");
    }
    reader.onload = function (e) {
        infoAppend(file.name + " loaded");
        v[0] = e.target.result;
        callback();
    };
    try {
        reader.readAsText(file);
    } catch (e) {
        infoAppend("Loading failed");
        console.error(e.message);
    }
}

let debugMode = false;
let chartLog;
let showChart = false;
let chartConainterDOM = document.getElementById("chart-container");
function start() {
    if (loading) return;
    loading = true;
    infoReset();
    uploadFile(roadnetData, RoadnetFileDom.files[0], function () {
        uploadFile(replayData, ReplayFileDom.files[0], function () {
            let after_update = function () {
                infoAppend("drawing roadnet");
                ready = false;
                document.getElementById("guide").classList.add("d-none");
                hideCanvas();
                try {
                    simulation = JSON.parse(roadnetData[0]);
                } catch (e) {
                    infoAppend("Parsing roadnet file failed");
                    loading = false;
                    return;
                }
                try {
                    logs = replayData[0].split('\n');
                    logs.pop();
                } catch (e) {
                    infoAppend("Reading replay file failed");
                    loading = false;
                    return;
                }

                totalStep = logs.length;
                if (showChart) {
                    chartConainterDOM.classList.remove("d-none");
                    let chart_lines = chartData[0].split('\n');
                    if (chart_lines.length == 0) {
                        infoAppend("Chart file is empty");
                        showChart = false;
                    }
                    chartLog = [];
                    for (let i = 0; i < totalStep; ++i) {
                        step_data = chart_lines[i + 1].split(/[ \t]+/);
                        chartLog.push([]);
                        for (let j = 0; j < step_data.length; ++j) {
                            chartLog[i].push(parseFloat(step_data[j]));
                        }
                    }
                    chart.init(chart_lines[0], chartLog[0].length, totalStep);
                } else {
                    chartConainterDOM.classList.add("d-none");
                }

                controls.paused = false;
                cnt = 0;
                debugMode = document.getElementById("debug-mode").checked;
                setTimeout(function () {
                    try {
                        drawRoadnet();
                    } catch (e) {
                        infoAppend("Drawing roadnet failed");
                        console.error(e.message);
                        loading = false;
                        return;
                    }
                    ready = true;
                    loading = false;
                    infoAppend("Start replaying");
                }, 200);
            };


            if (ChartFileDom.value) {
                showChart = true;
                uploadFile(chartData, ChartFileDom.files[0], after_update);
            } else {
                showChart = false;
                after_update();
            }

        }); // replay callback
    }); // roadnet callback
}

let RoadnetFileDom = document.getElementById("roadnet-file");
let ReplayFileDom = document.getElementById("replay-file");
let ChartFileDom = document.getElementById("chart-file");

RoadnetFileDom.addEventListener("change",
    handleChooseFile(roadnetData, document.getElementById("roadnet-label")), false);
ReplayFileDom.addEventListener("change",
    handleChooseFile(replayData, document.getElementById("replay-label")), false);
ChartFileDom.addEventListener("change",
    handleChooseFile(chartData, document.getElementById("chart-label")), false);

document.getElementById("start-btn").addEventListener("click", start);

document.getElementById("slow-btn").addEventListener("click", function () {
    updateReplaySpeed(controls.replaySpeed - 0.1);
})

document.getElementById("fast-btn").addEventListener("click", function () {
    updateReplaySpeed(controls.replaySpeed + 0.1);
})

function updateReplaySpeed(speed) {
    speed = Math.min(speed, 1);
    speed = Math.max(speed, 0);
    controls.replaySpeed = speed;
    replayControlDom.value = speed * 100;
    replaySpeedDom.innerHTML = speed.toFixed(2);
}

updateReplaySpeed(0.5);

replayControlDom.addEventListener('change', function (e) {
    updateReplaySpeed(replayControlDom.value / 100);
});

document.addEventListener('keydown', function (e) {
    if (e.keyCode == P) {
        controls.paused = !controls.paused;
    } else if (e.keyCode == ONE) {
        updateReplaySpeed(Math.max(controls.replaySpeed / 1.5, controls.replaySpeedMin));
    } else if (e.keyCode == TWO) {
        updateReplaySpeed(Math.min(controls.replaySpeed * 1.5, controls.replaySpeedMax));
    } else if (e.keyCode == LEFT_BRACKET) {
        cnt = (cnt - 1) % totalStep;
        cnt = (cnt + totalStep) % totalStep;
        drawStep(cnt);
    } else if (e.keyCode == RIGHT_BRACKET) {
        cnt = (cnt + 1) % totalStep;
        drawStep(cnt);
    } else {
        keyDown.add(e.keyCode)
    }
});

document.addEventListener('keyup', (e) => keyDown.delete(e.keyCode));

nodeCanvas.addEventListener('dblclick', function (e) {
    controls.paused = !controls.paused;
});

pauseButton.addEventListener('click', function (e) {
    controls.paused = !controls.paused;
});

// ===== VIDEO GENERATION CODE =====
const API_BASE_URL = 'http://localhost:5000/api';

let stateActionData = null;
let StateActionFileDom = document.getElementById("state-action-file");
let zoomControl = document.getElementById("zoom-control");
let zoomValue = document.getElementById("zoom-value");
let startStepInput = document.getElementById("start-step-input");
let endStepInput = document.getElementById("end-step-input");
let generateVideoBtn = document.getElementById("generate-video-btn");
let videoStatus = document.getElementById("video-status");
let videoStatusText = document.getElementById("video-status-text");
let videoList = document.getElementById("video-list");
let videoListContainer = document.getElementById("video-list-container");

// Handle state-action file selection
StateActionFileDom.addEventListener("change", function (evt) {
    let file = evt.target.files[0];
    if (file) {
        document.getElementById("state-action-label").innerText = file.name;
        stateActionData = file;
    }
}, false);

// Zoom control
zoomControl.addEventListener('input', function () {
    zoomValue.innerText = zoomControl.value;
});

document.getElementById("zoom-out-btn").addEventListener("click", function () {
    let val = parseInt(zoomControl.value);
    zoomControl.value = Math.max(50, val - 10);
    zoomValue.innerText = zoomControl.value;
});

document.getElementById("zoom-in-btn").addEventListener("click", function () {
    let val = parseInt(zoomControl.value);
    zoomControl.value = Math.min(200, val + 10);
    zoomValue.innerText = zoomControl.value;
});

// Generate video function
async function generateVideo() {
    // Validate required files
    if (!RoadnetFileDom.files[0]) {
        alert("Please upload a roadnet file first!");
        return;
    }
    if (!ReplayFileDom.files[0]) {
        alert("Please upload a replay file first!");
        return;
    }
    if (!stateActionData) {
        alert("Please upload a state-action file!");
        return;
    }

    // Get step range
    const startStep = parseInt(startStepInput.value) || 0;
    const endStepValue = endStepInput.value;
    let endStep = null;

    if (endStepValue && endStepValue.trim() !== '') {
        endStep = parseInt(endStepValue);
        if (endStep <= startStep) {
            alert("End step must be greater than start step!");
            return;
        }
    }

    // Show status
    videoStatus.classList.remove('d-none');
    const stepsText = endStep ? `${startStep} to ${endStep}` : `${startStep} to ${startStep + 300}`;
    videoStatusText.innerText = `Uploading files and starting generation (steps ${stepsText})...`;
    generateVideoBtn.disabled = true;

    try {
        // Prepare form data
        const formData = new FormData();
        formData.append('roadnet', RoadnetFileDom.files[0]);
        formData.append('replay', ReplayFileDom.files[0]);
        formData.append('log', stateActionData);
        formData.append('start_step', startStep);
        if (endStep !== null) {
            formData.append('end_step', endStep);
        } else {
            formData.append('steps', 300); // Default if no end_step
        }
        formData.append('zoom_level', zoomControl.value);
        formData.append('intersection', 'intersection_1_1'); // Default
        formData.append('interval', '30'); // Default

        // Make API call
        const response = await fetch(`${API_BASE_URL}/generate-video`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            const jobId = result.job_id;
            videoStatusText.innerText = "Video generation in progress...";

            // Poll for job status
            pollJobStatus(jobId, result.filename);
        } else {
            throw new Error(result.message || 'Unknown error');
        }
    } catch (error) {
        console.error('Video generation error:', error);
        videoStatusText.innerText = `Error: ${error.message}`;
        videoStatus.classList.remove('alert-info');
        videoStatus.classList.add('alert-danger');
        generateVideoBtn.disabled = false;
    }
}

// Poll job status
async function pollJobStatus(jobId, filename) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/video-status/${jobId}`);
            const result = await response.json();

            if (result.success) {
                if (result.status === 'completed') {
                    clearInterval(pollInterval);
                    videoStatusText.innerText = "Video generated successfully!";
                    videoStatus.classList.remove('alert-info');
                    videoStatus.classList.add('alert-success');
                    generateVideoBtn.disabled = false;

                    // Refresh video list
                    await loadVideoList();

                    // Hide status after 3 seconds
                    setTimeout(() => {
                        videoStatus.classList.add('d-none');
                        videoStatus.classList.remove('alert-danger', 'alert-success');
                        videoStatus.classList.add('alert-info');
                    }, 3000);
                } else if (result.status === 'failed') {
                    clearInterval(pollInterval);
                    videoStatusText.innerText = `Error: ${result.result?.message || 'Video generation failed'}`;
                    videoStatus.classList.remove('alert-info');
                    videoStatus.classList.add('alert-danger');
                    generateVideoBtn.disabled = false;
                }
                // If still processing, continue polling
            }
        } catch (error) {
            clearInterval(pollInterval);
            console.error('Status poll error:', error);
            videoStatusText.innerText = `Error checking status: ${error.message}`;
            videoStatus.classList.remove('alert-info');
            videoStatus.classList.add('alert-danger');
            generateVideoBtn.disabled = false;
        }
    }, 2000); // Poll every 2 seconds
}

// Load video list
async function loadVideoList() {
    try {
        const response = await fetch(`${API_BASE_URL}/videos`);
        const result = await response.json();

        if (result.success && result.videos.length > 0) {
            videoList.classList.remove('d-none');
            videoListContainer.innerHTML = '';

            result.videos.forEach(video => {
                const videoItem = document.createElement('a');
                videoItem.href = '#';
                videoItem.className = 'list-group-item list-group-item-action';
                videoItem.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${video.filename}</h6>
                        <small>${formatBytes(video.size)}</small>
                    </div>
                    <small class="text-muted">Created: ${new Date(video.created).toLocaleString()}</small>
                `;

                videoItem.addEventListener('click', (e) => {
                    e.preventDefault();
                    downloadVideo(video.filename);
                });

                videoListContainer.appendChild(videoItem);
            });
        }
    } catch (error) {
        console.error('Error loading video list:', error);
    }
}

// Download video
function downloadVideo(filename) {
    window.open(`${API_BASE_URL}/videos/${filename}`, '_blank');
}

// Helper function to format bytes
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Event listener for generate button
generateVideoBtn.addEventListener('click', generateVideo);

// Load video list on page load
window.addEventListener('load', loadVideoList);

// ===== END VIDEO GENERATION CODE =====


function initCanvas() {
    app = new Application({
        width: nodeCanvas.offsetWidth,
        height: nodeCanvas.offsetHeight,
        transparent: false,
        backgroundColor: BACKGROUND_COLOR
    });

    nodeCanvas.appendChild(app.view);
    app.view.classList.add("d-none");

    renderer = app.renderer;
    renderer.interactive = true;
    renderer.autoResize = true;

    renderer.resize(nodeCanvas.offsetWidth, nodeCanvas.offsetHeight);
    app.ticker.add(run);
}

function showCanvas() {
    document.getElementById("spinner").classList.add("d-none");
    app.view.classList.remove("d-none");
}

function hideCanvas() {
    document.getElementById("spinner").classList.remove("d-none");
    app.view.classList.add("d-none");
}

function drawRoadnet() {
    if (simulatorContainer) {
        simulatorContainer.destroy(true);
    }
    app.stage.removeChildren();
    viewport = new Viewport.Viewport({
        screenWidth: window.innerWidth,
        screenHeight: window.innerHeight,
        interaction: app.renderer.plugins.interaction
    });
    viewport
        .drag()
        .pinch()
        .wheel()
        .decelerate();
    app.stage.addChild(viewport);
    simulatorContainer = new Container();
    viewport.addChild(simulatorContainer);

    roadnet = simulation.static;
    if (!roadnet && simulation.intersections && simulation.roads) {
        roadnet = { nodes: [], edges: [] };
        for (let i = 0; i < simulation.intersections.length; i++) {
            let intersection = simulation.intersections[i];
            let node = {
                id: intersection.id,
                point: [intersection.point.x, intersection.point.y],
                virtual: intersection.virtual,
                width: intersection.width
            };
            if (!intersection.outline) {
                let w = intersection.width || 10;
                if (intersection.virtual) w = 5;
                let x = intersection.point.x;
                let y = intersection.point.y;
                node.outline = [
                    x - w / 2, y - w / 2,
                    x + w / 2, y - w / 2,
                    x + w / 2, y + w / 2,
                    x - w / 2, y + w / 2
                ];
            } else {
                node.outline = intersection.outline;
            }
            roadnet.nodes.push(node);
        }
        for (let i = 0; i < simulation.roads.length; i++) {
            let road = simulation.roads[i];
            let edge = {
                id: road.id,
                from: road.startIntersection,
                to: road.endIntersection,
                points: road.points.map(p => [p.x, p.y]),
                nLane: road.lanes.length,
                laneWidths: road.lanes.map(l => l.width)
            };
            roadnet.edges.push(edge);
        }
        simulation.static = roadnet;
    }
    nodes = [];
    edges = [];
    trafficLightsG = {};

    for (let i = 0, len = roadnet.nodes.length; i < len; ++i) {
        node = roadnet.nodes[i];
        node.point = new Point(transCoord(node.point));
        nodes[node.id] = node;
    }

    for (let i = 0, len = roadnet.edges.length; i < len; ++i) {
        edge = roadnet.edges[i];
        edge.from = nodes[edge.from];
        edge.to = nodes[edge.to];
        for (let j = 0, len = edge.points.length; j < len; ++j) {
            edge.points[j] = new Point(transCoord(edge.points[j]));
        }
        edges[edge.id] = edge;
    }

    /**
     * Draw Map
     */
    trafficLightContainer = new ParticleContainer(MAX_TRAFFIC_LIGHT_NUM, { tint: true });
    let mapContainer, mapGraphics;
    if (debugMode) {
        mapContainer = new Container();
        simulatorContainer.addChild(mapContainer);
    } else {
        mapGraphics = new Graphics();
        simulatorContainer.addChild(mapGraphics);
    }

    for (nodeId in nodes) {
        if (!nodes[nodeId].virtual) {
            let nodeGraphics;
            if (debugMode) {
                nodeGraphics = new Graphics();
                mapContainer.addChild(nodeGraphics);
            } else {
                nodeGraphics = mapGraphics;
            }
            drawNode(nodes[nodeId], nodeGraphics);
        }
    }
    for (edgeId in edges) {
        let edgeGraphics;
        if (debugMode) {
            edgeGraphics = new Graphics();
            mapContainer.addChild(edgeGraphics);
        } else {
            edgeGraphics = mapGraphics;
        }
        drawEdge(edges[edgeId], edgeGraphics);
    }
    let bounds = simulatorContainer.getBounds();
    simulatorContainer.pivot.set(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
    simulatorContainer.position.set(renderer.width / 2, renderer.height / 2);
    simulatorContainer.addChild(trafficLightContainer);

    /**
     * Settings for Cars
     */
    TURN_SIGNAL_LENGTH = CAR_LENGTH;
    TURN_SIGNAL_WIDTH = CAR_WIDTH / 2;

    var carG = new Graphics();
    carG.lineStyle(0);
    carG.beginFill(0xFFFFFF, 0.8);
    carG.drawRect(0, 0, CAR_LENGTH, CAR_WIDTH);

    let carTexture = renderer.generateTexture(carG);

    let signalG = new Graphics();
    signalG.beginFill(TURN_SIGNAL_COLOR, 0.7).drawRect(0, 0, TURN_SIGNAL_LENGTH, TURN_SIGNAL_WIDTH)
        .drawRect(0, 3 * CAR_WIDTH - TURN_SIGNAL_WIDTH, TURN_SIGNAL_LENGTH, TURN_SIGNAL_WIDTH).endFill();
    let turnSignalTexture = renderer.generateTexture(signalG);

    let signalLeft = new Texture(turnSignalTexture, new Rectangle(0, 0, TURN_SIGNAL_LENGTH, CAR_WIDTH));
    let signalStraight = new Texture(turnSignalTexture, new Rectangle(0, CAR_WIDTH, TURN_SIGNAL_LENGTH, CAR_WIDTH));
    let signalRight = new Texture(turnSignalTexture, new Rectangle(0, CAR_WIDTH * 2, TURN_SIGNAL_LENGTH, CAR_WIDTH));
    turnSignalTextures = [signalLeft, signalStraight, signalRight];


    carPool = [];
    if (debugMode)
        carContainer = new Container();
    else
        carContainer = new ParticleContainer(NUM_CAR_POOL, { rotation: true, tint: true });


    turnSignalContainer = new ParticleContainer(NUM_CAR_POOL, { rotation: true, tint: true });
    simulatorContainer.addChild(carContainer);
    simulatorContainer.addChild(turnSignalContainer);
    for (let i = 0, len = NUM_CAR_POOL; i < len; ++i) {
        //var car = Sprite.fromImage("images/car.png")
        let car = new Sprite(carTexture);
        let signal = new Sprite(turnSignalTextures[1]);
        car.anchor.set(1, 0.5);

        if (debugMode) {
            car.interactive = true;
            car.on('mouseover', function () {
                selectedDOM.innerText = car.name;
                car.alpha = 0.8;
            });
            car.on('mouseout', function () {
                // selectedDOM.innerText = "";
                car.alpha = 1;
            });
        }
        signal.anchor.set(1, 0.5);
        carPool.push([car, signal]);
    }
    showCanvas();

    return true;
}

function appendText(id, text) {
    let p = document.createElement("span");
    p.innerText = text;
    document.getElementById("info").appendChild(p);
    document.getElementById("info").appendChild(document.createElement("br"));
}

var statsFile = "";
var withRange = false;
var nodeStats, nodeRange;

initCanvas();


function transCoord(point) {
    return [point[0], -point[1]];
}

PIXI.Graphics.prototype.drawLine = function (pointA, pointB) {
    this.moveTo(pointA.x, pointA.y);
    this.lineTo(pointB.x, pointB.y);
}

PIXI.Graphics.prototype.drawDashLine = function (pointA, pointB, dash = 16, gap = 8) {
    let direct = pointA.directTo(pointB);
    let distance = pointA.distanceTo(pointB);

    let currentPoint = pointA;
    let currentDistance = 0;
    let length;
    let finish = false;
    while (true) {
        this.moveTo(currentPoint.x, currentPoint.y);
        if (currentDistance + dash >= distance) {
            length = distance - currentDistance;
            finish = true;
        } else {
            length = dash
        }
        currentPoint = currentPoint.moveAlong(direct, length);
        this.lineTo(currentPoint.x, currentPoint.y);
        if (finish) break;
        currentDistance += length;

        if (currentDistance + gap >= distance) {
            break;
        } else {
            currentPoint = currentPoint.moveAlong(direct, gap);
            currentDistance += gap;
        }
    }
};

function drawNode(node, graphics) {
    graphics.beginFill(LANE_COLOR);
    let outline = node.outline;
    for (let i = 0; i < outline.length; i += 2) {
        outline[i + 1] = -outline[i + 1];
        if (i == 0)
            graphics.moveTo(outline[i], outline[i + 1]);
        else
            graphics.lineTo(outline[i], outline[i + 1]);
    }
    graphics.endFill();

    if (debugMode) {
        graphics.hitArea = new PIXI.Polygon(outline);
        graphics.interactive = true;
        graphics.on("mouseover", function () {
            selectedDOM.innerText = node.id;
            graphics.alpha = 0.5;
        });
        graphics.on("mouseout", function () {
            graphics.alpha = 1;
        });
    }

}

function drawEdge(edge, graphics) {
    let from = edge.from;
    let to = edge.to;
    let points = edge.points;

    let pointA, pointAOffset, pointB, pointBOffset;
    let prevPointBOffset = null;

    let roadWidth = 0;
    edge.laneWidths.forEach(function (l) {
        roadWidth += l;
    }, 0);

    let coords = [], coords1 = [];

    for (let i = 1; i < points.length; ++i) {
        if (i == 1) {
            pointA = points[0].moveAlongDirectTo(points[1], from.virtual ? 0 : from.width);
            pointAOffset = points[0].directTo(points[1]).rotate(ROTATE);
        } else {
            pointA = points[i - 1];
            pointAOffset = prevPointBOffset;
        }
        if (i == points.length - 1) {
            pointB = points[i].moveAlongDirectTo(points[i - 1], to.virtual ? 0 : to.width);
            pointBOffset = points[i - 1].directTo(points[i]).rotate(ROTATE);
        } else {
            pointB = points[i];
            pointBOffset = points[i - 1].directTo(points[i + 1]).rotate(ROTATE);
        }
        prevPointBOffset = pointBOffset;

        lightG = new Graphics();
        lightG.lineStyle(TRAFFIC_LIGHT_WIDTH, 0xFFFFFF);
        lightG.drawLine(new Point(0, 0), new Point(1, 0));
        lightTexture = renderer.generateTexture(lightG);

        // Draw Traffic Lights
        if (i == points.length - 1 && !to.virtual) {
            edgeTrafficLights = [];
            prevOffset = offset = 0;
            for (lane = 0; lane < edge.nLane; ++lane) {
                offset += edge.laneWidths[lane];
                var light = new Sprite(lightTexture);
                light.anchor.set(0, 0.5);
                light.scale.set(offset - prevOffset, 1);
                point_ = pointB.moveAlong(pointBOffset, prevOffset);
                light.position.set(point_.x, point_.y);
                light.rotation = pointBOffset.getAngleInRadians();
                edgeTrafficLights.push(light);
                prevOffset = offset;
                trafficLightContainer.addChild(light);
            }
            trafficLightsG[edge.id] = edgeTrafficLights;
        }

        // Draw Roads
        graphics.lineStyle(LANE_BORDER_WIDTH, LANE_BORDER_COLOR, 1);
        graphics.drawLine(pointA, pointB);

        pointA1 = pointA.moveAlong(pointAOffset, roadWidth);
        pointB1 = pointB.moveAlong(pointBOffset, roadWidth);

        graphics.lineStyle(0);
        graphics.beginFill(LANE_COLOR);

        coords = coords.concat([pointA.x, pointA.y, pointB.x, pointB.y]);
        coords1 = coords1.concat([pointA1.y, pointA1.x, pointB1.y, pointB1.x]);

        graphics.drawPolygon([pointA.x, pointA.y, pointB.x, pointB.y, pointB1.x, pointB1.y, pointA1.x, pointA1.y]);
        graphics.endFill();

        offset = 0;
        for (let lane = 0, len = edge.nLane - 1; lane < len; ++lane) {
            offset += edge.laneWidths[lane];
            graphics.lineStyle(LANE_BORDER_WIDTH, LANE_INNER_COLOR);
            graphics.drawDashLine(pointA.moveAlong(pointAOffset, offset), pointB.moveAlong(pointBOffset, offset), LANE_DASH, LANE_GAP);
        }

        offset += edge.laneWidths[edge.nLane - 1];

        // graphics.lineStyle(LANE_BORDER_WIDTH, LANE_BORDER_COLOR);
        // graphics.drawLine(pointA.moveAlong(pointAOffset, offset), pointB.moveAlong(pointBOffset, offset));
    }

    if (debugMode) {
        coords = coords.concat(coords1.reverse());
        graphics.interactive = true;
        graphics.hitArea = new PIXI.Polygon(coords);
        graphics.on("mouseover", function () {
            graphics.alpha = 0.5;
            selectedDOM.innerText = edge.id;
        });

        graphics.on("mouseout", function () {
            graphics.alpha = 1;
        });
    }
}

function run(delta) {
    let redraw = false;

    if (ready && (!controls.paused || redraw)) {
        try {
            drawStep(cnt);
        } catch (e) {
            infoAppend("Error occurred when drawing");
            ready = false;
        }
        if (!controls.paused) {
            frameElapsed += 1;
            if (frameElapsed >= 1 / controls.replaySpeed ** 2) {
                cnt += 1;
                frameElapsed = 0;
                if (cnt == totalStep) cnt = 0;
            }
        }
    }
}

function _statusToColor(status) {
    switch (status) {
        case 'r':
            return LIGHT_RED;
        case 'g':
            return LIGHT_GREEN;
        default:
            return 0x808080;
    }
}

function stringHash(str) {
    let hash = 0;
    let p = 127, p_pow = 1;
    let m = 1e9 + 9;
    for (let i = 0; i < str.length; i++) {
        hash = (hash + str.charCodeAt(i) * p_pow) % m;
        p_pow = (p_pow * p) % m;
    }
    return hash;
}

function drawStep(step) {
    if (showChart && (step > chart.ptr || step == 0)) {
        if (step == 0) {
            chart.clear();
        }
        chart.ptr = step;
        chart.addData(chartLog[step]);
    }

    let [carLogs, tlLogs] = logs[step].split(';');

    tlLogs = tlLogs.split(',');
    carLogs = carLogs.split(',');

    let tlLog, tlEdge, tlStatus;
    for (let i = 0, len = tlLogs.length; i < len; ++i) {
        tlLog = tlLogs[i].split(' ');
        tlEdge = tlLog[0];
        tlStatus = tlLog.slice(1);
        for (let j = 0, len = tlStatus.length; j < len; ++j) {
            trafficLightsG[tlEdge][j].tint = _statusToColor(tlStatus[j]);
            if (tlStatus[j] == 'i') {
                trafficLightsG[tlEdge][j].alpha = 0;
            } else {
                trafficLightsG[tlEdge][j].alpha = 1;
            }
        }
    }

    carContainer.removeChildren();
    turnSignalContainer.removeChildren();
    let carLog, position, length, width;
    for (let i = 0, len = carLogs.length - 1; i < len; ++i) {
        carLog = carLogs[i].split(' ');
        position = transCoord([parseFloat(carLog[0]), parseFloat(carLog[1])]);
        length = parseFloat(carLog[5]);
        width = parseFloat(carLog[6]);
        carPool[i][0].position.set(position[0], position[1]);
        carPool[i][0].rotation = 2 * Math.PI - parseFloat(carLog[2]);
        carPool[i][0].name = carLog[3];
        let carColorId = stringHash(carLog[3]) % CAR_COLORS_NUM;
        carPool[i][0].tint = CAR_COLORS[carColorId];
        carPool[i][0].width = length;
        carPool[i][0].height = width;
        carContainer.addChild(carPool[i][0]);

        let laneChange = parseInt(carLog[4]) + 1;
        carPool[i][1].position.set(position[0], position[1]);
        carPool[i][1].rotation = carPool[i][0].rotation;
        carPool[i][1].texture = turnSignalTextures[laneChange];
        carPool[i][1].width = length;
        carPool[i][1].height = width;
        turnSignalContainer.addChild(carPool[i][1]);
    }
    nodeCarNum.innerText = carLogs.length - 1;
    nodeTotalStep.innerText = totalStep;
    nodeCurrentStep.innerText = cnt + 1;
    nodeProgressPercentage.innerText = (cnt / totalStep * 100).toFixed(2) + "%";
    if (statsFile != "") {
        if (withRange) nodeRange.value = stats[step][1];
        nodeStats.innerText = stats[step][0].toFixed(2);
    }
}

/*
Chart
 */
let chart = {
    max_steps: 3600,
    data: {
        labels: [],
        series: [[]]
    },
    options: {
        showPoint: false,
        lineSmooth: false,
        axisX: {
            showGrid: false,
            showLabel: false
        }
    },
    init: function (title, series_cnt, max_step) {
        document.getElementById("chart-title").innerText = title;
        this.max_steps = max_step;
        this.data.labels = new Array(this.max_steps);
        this.data.series = [];
        for (let i = 0; i < series_cnt; ++i)
            this.data.series.push([]);
        this.chart = new Chartist.Line('#chart', this.data, this.options);
    },
    addData: function (value) {
        for (let i = 0; i < value.length; ++i) {
            this.data.series[i].push(value[i]);
            if (this.data.series[i].length > this.max_steps) {
                this.data.series[i].shift();
            }
        }
        this.chart.update();
    },
    clear: function () {
        for (let i = 0; i < this.data.series.length; ++i)
            this.data.series[i] = [];
    },
    ptr: 0
};
