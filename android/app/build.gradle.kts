plugins {
    id("com.android.application")
    id("com.chaquo.python")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.cycling.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.cycling.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            install("fastapi")
            install("uvicorn")
            install("jinja2")
            install("python-multipart")
            install("rich")
            install("typer")
        }
    }
}

val copyPythonSource by tasks.registering(Copy::class) {
    from("${rootProject.projectDir}/../src/cycling")
    into("src/main/python/cycling")
}
tasks.matching { it.name.startsWith("merge") && it.name.endsWith("PythonSources") }.configureEach {
    dependsOn(copyPythonSource)
}

dependencies {
    implementation("androidx.webkit:webkit:1.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.activity:activity-ktx:1.8.2")

    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
}
